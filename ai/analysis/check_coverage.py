#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
时间线覆盖检查脚本

检测AI是否漏掉了某些时段的理解记录。
比较 perception.jsonl 中最晚事件时间和 理解.md 中最晚时段时间。

用法:
    python ai/analysis/check_coverage.py <日期>
    python ai/analysis/check_coverage.py <日期> --json
    python ai/analysis/check_coverage.py <日期> --quiet

退出码:
    0 = 通过 (覆盖完整)
    1 = 漏时段 (理解文件缺失或缺口超过2小时)
    2 = 数据不完整 (原始数据本身采集不完整)

依赖: 仅标准库
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DATA_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, '..', 'data'))


def parse_time(t_str):
    """将 HH:MM:SS 或 HH:MM 格式的时间转换为秒数

    Args:
        t_str: 时间字符串, 如 "23:59:59" 或 "22:00"

    Returns:
        int: 从00:00:00开始的秒数, 解析失败返回 None
    """
    parts = t_str.strip().split(':')
    if len(parts) == 2:
        h, m = parts
        s = '0'
    elif len(parts) == 3:
        h, m, s = parts
    else:
        return None
    try:
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, IndexError):
        return None


def format_time(seconds):
    """将秒数格式化为 HH:MM:SS"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_raw_time_range(date_str, base_dir='data'):
    """从 perception.jsonl 获取最早和最晚事件时间

    perception.jsonl 每行一个JSON对象, 包含 t 字段 (HH:MM:SS 格式)。

    Args:
        date_str: 日期字符串 YYYY-MM-DD
        base_dir: 数据根目录

    Returns:
        tuple: (first_seconds, last_seconds, last_t_str) 或 (None, None, error_message)
    """
    perception_path = os.path.join(base_dir, date_str, 'perception.jsonl')
    if not os.path.exists(perception_path):
        return None, None, f"perception.jsonl 不存在: {perception_path}"

    first_t = None
    last_t = None
    last_raw = None
    try:
        with open(perception_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    t_str = obj.get('t', '')
                    if t_str:
                        seconds = parse_time(t_str)
                        if seconds is not None:
                            if first_t is None or seconds < first_t:
                                first_t = seconds
                            if last_t is None or seconds > last_t:
                                last_t = seconds
                                last_raw = t_str
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return None, None, f"读取 perception.jsonl 失败: {e}"

    if last_t is None:
        return None, None, f"perception.jsonl 中没有找到有效时间数据"

    return first_t, last_t, last_raw


def get_understood_last_time(date_str, base_dir='data'):
    """从 理解.md 获取最晚理解时段结束时间

    理解文件命名支持两种模式:
    1. {date}/理解.md
    2. {date}/{date}-理解.md

    时段标题格式: ## HH:MM~HH:MM (说明文字)

    Args:
        date_str: 日期字符串 YYYY-MM-DD
        base_dir: 数据根目录

    Returns:
        tuple: (end_seconds, start_str, end_str) 或 (None, None, reason)
            - end_seconds: 最晚时段结束时间的秒数
            - start_str: 最晚时段的开始时间字符串
            - end_str: 最晚时段的结束时间字符串
    """
    date_dir = os.path.join(base_dir, date_str)

    # 尝试两种常见的文件名
    candidates = [
        os.path.join(date_dir, '理解.md'),
        os.path.join(date_dir, f'{date_str}-理解.md'),
    ]

    # 也尝试匹配目录下所有包含"理解"的md文件
    understood_path = None
    for p in candidates:
        if os.path.exists(p):
            understood_path = p
            break

    # 如果标准命名没找到, 模糊搜索目录
    if understood_path is None and os.path.isdir(date_dir):
        try:
            for fname in os.listdir(date_dir):
                fpath = os.path.join(date_dir, fname)
                if os.path.isfile(fpath) and fname.endswith('.md') and \
                   ('理解' in fname or '理解' in fname):
                    understood_path = fpath
                    break
        except OSError:
            pass

    if understood_path is None:
        return None, None, "理解文件不存在"

    try:
        with open(understood_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, None, f"读取理解文件失败: {e}"

    # 匹配 ## HH:MM~HH:MM 格式的时段标题
    # 时段分隔符可能是 ~ 或 - 或 ~
    pattern = r'##\s+(\d{1,2}:\d{2})\s*[~\-\u223c]\s*(\d{1,2}:\d{2})'
    matches = re.findall(pattern, content)

    if not matches:
        return None, None, "理解文件中没有找到时段信息"

    # 取最后一个时段
    last_start_str, last_end_str = matches[-1]
    last_end_seconds = parse_time(last_end_str)
    last_start_seconds = parse_time(last_start_str)

    if last_end_seconds is None:
        return None, None, f"无法解析最晚时段结束时间: {last_end_str}"

    # 处理跨午夜的情况: 23:50~00:00 表示结束于 24:00
    # 如果结束时间小于开始时间, 说明是跨天时段, 结束时间 + 24h
    if last_start_seconds is not None and last_end_seconds < last_start_seconds:
        last_end_seconds += 86400  # 加一天

    # 处理午夜时段特例: 如果最后时段从00:00开始且结束时间<12:00,
    # 说明是当天的午夜过渡时段, 加24h以正确比较
    if last_start_seconds == 0 and last_end_seconds is not None and last_end_seconds < 43200:
        last_end_seconds += 86400

    return last_end_seconds, last_start_str, last_end_str


def check_data_completeness(raw_first_seconds, raw_last_seconds, date_str):
    """判断当天原始数据是否采集完整

    对于已过去的日期:
    1. 如果最早数据时间晚于 08:00, 说明数据采集开始过晚
    2. 如果最晚数据时间早于 23:00, 说明采集在晚上提前结束

    对于今天, 数据可能还在收集中, 返回完整。

    Args:
        raw_first_seconds: 原始数据最早时间(秒)
        raw_last_seconds: 原始数据最晚时间(秒)
        date_str: 日期字符串

    Returns:
        tuple: (is_complete, reason)
    """
    # 对于今天, 数据可能还在收集中
    today_str = datetime.now().strftime('%Y-%m-%d')
    if date_str == today_str:
        return True, None

    # 检查最早时间: 如果数据从上午很晚才开始, 说明不完整
    late_start_threshold = 8 * 3600  # 08:00
    if raw_first_seconds is not None and raw_first_seconds >= late_start_threshold:
        return False, (
            f"数据采集开始过晚, 最早数据时间: {format_time(raw_first_seconds)}, "
            f"最晚: {format_time(raw_last_seconds)}"
        )

    # 检查最晚时间: 如果结束时间早于 23:00
    evening_threshold = 23 * 3600  # 23:00
    if raw_last_seconds < evening_threshold:
        return False, f"数据采集提前结束, 最晚数据时间: {format_time(raw_last_seconds)}"

    # 数据覆盖完整
    return True, None


def check_internal_gaps(date_str, base_dir='data', raw_first_seconds=None, raw_last_seconds=None):
    """检查理解文件内部是否有缺口

    解析理解文件中所有时段，检查：
    1. 时段之间是否有缺口（超过2小时无理解记录）
    2. 理解覆盖是否从原始数据开始到结束

    Args:
        date_str: 日期字符串 YYYY-MM-DD
        base_dir: 数据根目录
        raw_first_seconds: 原始数据最早时间(秒)
        raw_last_seconds: 原始数据最晚时间(秒)

    Returns:
        tuple: (passed, gaps_list)
            - passed: True表示无缺口
            - gaps_list: 缺口列表，每个缺口为(缺口起始, 缺口结束, 缺口时长秒数)
    """
    date_dir = os.path.join(base_dir, date_str)
    gaps = []

    # 找理解文件
    candidates = [
        os.path.join(date_dir, '理解.md'),
        os.path.join(date_dir, f'{date_str}-理解.md'),
    ]
    understood_path = None
    for p in candidates:
        if os.path.exists(p):
            understood_path = p
            break
    if understood_path is None and os.path.isdir(date_dir):
        for fname in os.listdir(date_dir):
            fpath = os.path.join(date_dir, fname)
            if os.path.isfile(fpath) and fname.endswith('.md') and '理解' in fname:
                understood_path = fpath
                break
    if understood_path is None:
        return False, [('N/A', 'N/A', 0, '理解文件不存在')]

    with open(understood_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'##\s+(\d{1,2}:\d{2})\s*[~\-\u223c]\s*(\d{1,2}:\d{2})'
    matches = re.findall(pattern, content)
    if not matches:
        return False, [('N/A', 'N/A', 0, '未找到时段信息')]

    # 解析所有时段为秒并排序
    slots = []
    for start_str, end_str in matches:
        start_s = parse_time(start_str)
        end_s = parse_time(end_str)
        if start_s is None or end_s is None:
            continue
        # 跨午夜处理: end < start 说明跨天
        if end_s < start_s:
            end_s += 86400
        slots.append((start_s, end_s, start_str, end_str))

    if not slots:
        return True, []

    # 按开始时间排序
    slots.sort(key=lambda x: x[0])

    # 处理午夜时段: 如果某个时段从00:00开始且前面有晚间的段
    # 说明这个00:00是下一日的开始, 加86400
    for i in range(1, len(slots)):
        if slots[i][0] == 0 and slots[i][0] < slots[i-1][0]:
            s, e, ss, es = slots[i]
            slots[i] = (s + 86400, e + 86400, ss, es)

    # 检查从原始数据开始到第一个时段的缺口
    gap_threshold = 7200  # 2小时
    if raw_first_seconds is not None and slots[0][0] > raw_first_seconds + gap_threshold:
        gap_start = format_time(raw_first_seconds)
        gap_end = slots[0][2]
        gap_sec = slots[0][0] - raw_first_seconds
        gaps.append((gap_start, gap_end, gap_sec, '数据开始到首段理解'))

    # 检查时段之间的缺口
    for i in range(1, len(slots)):
        prev_end = slots[i-1][1]
        curr_start = slots[i][0]
        if curr_start > prev_end + gap_threshold:
            gap_start = slots[i-1][3]
            gap_end = slots[i][2]
            gap_sec = curr_start - prev_end
            gaps.append((gap_start, gap_end, gap_sec, '理解时段之间'))

    # 检查最后时段到原始数据结束的缺口
    if raw_last_seconds is not None:
        last_end = slots[-1][1]
        if last_end < raw_last_seconds - gap_threshold:
            gap_start = slots[-1][3]
            gap_end = format_time(raw_last_seconds)
            gap_sec = raw_last_seconds - last_end
            gaps.append((gap_start, gap_end, gap_sec, '最后时段到数据结束'))

    return len(gaps) == 0, gaps


def main():
    parser = argparse.ArgumentParser(
        description='时间线覆盖检查 - 检测AI是否漏掉了某些时段的感知理解记录'
    )
    parser.add_argument('date', help='日期, 格式: YYYY-MM-DD')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--quiet', action='store_true', help='安静模式, 只返回退出码')
    parser.add_argument(
        '--data-dir', default=_DEFAULT_DATA_DIR,
        help=f'数据目录 (默认: {_DEFAULT_DATA_DIR})'
    )

    args = parser.parse_args()
    date_str = args.date

    # ---- 1. 获取原始数据时间范围 ----
    raw_first_seconds, raw_last_seconds, raw_last_str = get_raw_time_range(
        date_str, args.data_dir
    )
    raw_first_str = format_time(raw_first_seconds) if raw_first_seconds is not None else None

    if raw_last_seconds is None:
        # perception.jsonl 本身不存在或无法读取
        if args.json:
            print(json.dumps({
                'date': date_str,
                'status': 'error',
                'reason': raw_last_str
            }, ensure_ascii=False))
        elif not args.quiet:
            print(f"[check_coverage] {date_str}")
            print(f"错误: {raw_last_str}")
        sys.exit(2)

    # ---- 2. 检查数据完整性 ----
    data_complete, incomplete_reason = check_data_completeness(
        raw_first_seconds, raw_last_seconds, date_str
    )

    if not data_complete:
        if args.json:
            print(json.dumps({
                'date': date_str,
                'raw_last': raw_last_str,
                'understood_last': None,
                'gap_seconds': None,
                'status': 'incomplete',
                'reason': incomplete_reason
            }, ensure_ascii=False))
        elif not args.quiet:
            print(f"[check_coverage] {date_str}")
            print(f"原始数据: {raw_first_str} ~ {raw_last_str}")
            print(f"状态: 数据不完整")
            print(f"原因: {incomplete_reason}")
        sys.exit(2)

    # ---- 3. 检查内部缺口（所有时段之间的间隙）----
    internal_ok, internal_gaps = check_internal_gaps(
        date_str, args.data_dir, raw_first_seconds, raw_last_seconds
    )

    if not internal_ok:
        gap_details = '; '.join([
            f'{g[0]}~{g[1]}({format_time(g[2])})[{g[3]}]'
            for g in internal_gaps
        ])
        if args.json:
            print(json.dumps({
                'date': date_str,
                'raw_range': f'{raw_first_str}~{raw_last_str}',
                'status': 'fail',
                'reason': f'内部缺口: {gap_details}'
            }, ensure_ascii=False))
        elif not args.quiet:
            print(f"[check_coverage] {date_str}")
            print(f"原始数据: {raw_first_str} ~ {raw_last_str}")
            print(f"状态: 未通过 - 理解文件内部存在缺口")
            for g in internal_gaps:
                print(f"  缺口: {g[0]}~{g[1]} ({format_time(g[2])}) [{g[3]}]")
        sys.exit(1)

    # ---- 4. 获取理解文件最晚时段 ----
    understood_last_seconds, last_start_str, last_end_str = get_understood_last_time(
        date_str, args.data_dir
    )

    # ---- 4. 对比判断 ----
    if understood_last_seconds is None:
        # 理解文件不存在
        gap_seconds = raw_last_seconds
        reason = f"理解文件不存在, 原始数据最晚: {raw_last_str}"
        if args.json:
            print(json.dumps({
                'date': date_str,
                'raw_last': raw_last_str,
                'understood_last': None,
                'gap_seconds': gap_seconds,
                'status': 'fail',
                'reason': reason
            }, ensure_ascii=False))
        elif not args.quiet:
            print(f"[check_coverage] {date_str}")
            print(f"原始数据最晚: {raw_last_str}")
            print(f"理解文件: 不存在")
            if raw_last_seconds > 0:
                print(f"缺口: ~{format_time(gap_seconds)} 未覆盖")
        sys.exit(1)

    # 计算缺口
    gap_seconds = raw_last_seconds - understood_last_seconds
    gap_threshold = 7200  # 2小时

    if gap_seconds > gap_threshold:
        # 漏时段
        gap_start = last_end_str
        gap_end = raw_last_str
        reason = f"未覆盖时段 {gap_start}~{gap_end} (缺口 {format_time(gap_seconds)})"

        if args.json:
            print(json.dumps({
                'date': date_str,
                'raw_last': raw_last_str,
                'understood_last': f"{last_start_str}~{last_end_str}",
                'gap_seconds': gap_seconds,
                'status': 'fail',
                'reason': reason
            }, ensure_ascii=False))
        elif not args.quiet:
            hours = gap_seconds / 3600
            print(f"[check_coverage] {date_str}")
            print(f"原始数据最晚: {raw_last_str}")
            print(f"理解文件最晚: {last_start_str} (时段结束 {last_end_str})")
            print(f"缺口: {raw_last_str} - {last_end_str} = ~{hours:.1f}h -> 未通过")
            print(f"原因: {reason}")
        sys.exit(1)

    # 通过
    if args.json:
        print(json.dumps({
            'date': date_str,
            'raw_last': raw_last_str,
            'understood_last': f"{last_start_str}~{last_end_str}",
            'gap_seconds': 0,
            'status': 'pass',
            'reason': '覆盖完整'
        }, ensure_ascii=False))
    elif not args.quiet:
        print(f"[check_coverage] {date_str}")
        print(f"原始数据最晚: {raw_last_str}")
        print(f"理解文件最晚: {last_start_str} (时段结束 {last_end_str})")
        print(f"缺口: 0s -> 通过")
    sys.exit(0)


if __name__ == '__main__':
    main()
