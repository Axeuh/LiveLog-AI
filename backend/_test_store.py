"""Test message store flow"""
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient(verify=False) as c:
        r = await c.post('https://localhost:8768/login', json={'username':'Axeuh','password':''})
        token = r.json().get('token','')
        headers = {'Authorization': f'Bearer {token}'}
        
        # Check sessions
        r = await c.get('https://localhost:8768/api/screen/session/list', headers=headers)
        print(f'Sessions: {r.json()}')
        
        # Check messages directly
        r = await c.get('https://localhost:8768/api/screen/session/omp_default/messages', headers=headers)
        j = r.json()
        msgs = j.get('messages') or j.get('data',{}).get('messages',[])
        print(f'Messages before send: {len(msgs)}')
        
        # Send a message
        r = await c.post('https://localhost:8768/api/screen/session/message', 
            json={'message':'Hello OMP','session_id':'omp_default'}, headers=headers)
        print(f'Send: {r.status_code} {r.json()}')
        
        await asyncio.sleep(5)
        
        # Check messages again
        r = await c.get('https://localhost:8768/api/screen/session/omp_default/messages', headers=headers)
        j = r.json()
        msgs = j.get('messages') or j.get('data',{}).get('messages',[])
        print(f'Messages after send: {len(msgs)}')
        for m in msgs:
            role = m.get('role','?')
            content = (m.get('content') or '')[:50]
            parts = m.get('parts',[])
            print(f'  [{role}] content={content!r} parts={len(parts)}')

asyncio.run(test())
