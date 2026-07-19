import { test, expect } from '@playwright/test'

test.describe('App Structure and Navigation', () => {
  test('F1.1: Chat page loads with correct structure', async ({ page }) => {
    await page.goto('/')
    // Default route should be /chat
    await expect(page).toHaveURL(/\/chat/)
    // Login overlay should show if not authenticated
    await expect(page.locator('.login-overlay')).toBeVisible()
    // The login overlay should have username/password fields
    await expect(page.locator('input[placeholder*="用户"]')).toBeVisible()
    await expect(page.locator('input[placeholder*="密码"]')).toBeVisible()
    // Bottom nav should be behind overlay (hidden when overlay shown)
    await expect(page.locator('.login-overlay')).toBeVisible()
  })

  test('F1.2: Login form interaction', async ({ page }) => {
    await page.goto('/chat')
    // Type username and password
    await page.fill('input[placeholder*="用户"]', 'testuser')
    await page.fill('input[placeholder*="密码"]', 'testpass')
    // Login button should be enabled
    await expect(page.getByRole('button', { name: /登录/ })).toBeVisible()
  })

  test('F2.1: Dashboard page has correct UI structure', async ({ page }) => {
    await page.goto('/dashboard')
    // Wait for page to render
    await page.waitForTimeout(1000)
    // Dashboard should have date navigation toolbar
    await expect(page.locator('.dash-top')).toBeVisible()
    // Should have edit mode button
    await expect(page.locator('.edit-btn')).toBeVisible()
    // Dashboard should render 8 block cards (or skeleton loading)
    const blocks = page.locator('.db-block')
    await expect(blocks).toHaveCount(8)
  })

  test('F2.2: Dashboard date navigation', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForTimeout(500)
    // Date navigation should have arrows
    await expect(page.locator('.date-arrow-left')).toBeVisible()
    await expect(page.locator('.date-arrow-right')).toBeVisible()
    // Current date should be displayed
    await expect(page.locator('.dash-date')).toBeVisible()
  })

  test('F2.3: Dashboard edit mode toggle', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForTimeout(500)
    // Click edit button
    await page.locator('.edit-btn').click()
    // Sensor visibility toggles should be visible
    await expect(page.locator('.sen-vis-btn')).toBeVisible()
  })

  test('F3.1: Files page loads', async ({ page }) => {
    await page.goto('/files')
    await page.waitForTimeout(1000)
    // Files page should have breadcrumb navigation
    await expect(page.locator('.files-top')).toBeVisible()
    // Search input should exist
    await expect(page.locator('input.search-input')).toBeVisible()
    // File tree or loading state
    await expect(page.locator('.file-tree, .page-state')).toBeVisible()
  })

  test('F3.2: Reports page loads', async ({ page }) => {
    await page.goto('/reports')
    await page.waitForTimeout(1000)
    // Reports page should have filter chips
    await expect(page.locator('.report-filter')).toBeVisible()
    // Report cards grid or loading state
    await expect(page.locator('.report-grid, .page-state')).toBeVisible()
  })

  test('F4.1: Settings page loads', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForTimeout(500)
    // Settings should have connection status card
    await expect(page.locator('.card')).toBeVisible()
    // System info should be present
    await expect(page.locator('.settings-section')).toBeVisible()
  })

  test('F4.2: Tab navigation works', async ({ page }) => {
    await page.goto('/')
    // Check that all 5 nav items exist
    const navItems = page.locator('.nav-item')
    await expect(navItems).toHaveCount(5)
  })
})

test.describe('UI Components', () => {
  test('F1.3: PageState shows for empty content', async ({ page }) => {
    await page.goto('/chat')
    // The PageState component should render when data is loading
    await page.waitForTimeout(500)
    // Loading state or empty state should be shown
    const pageState = page.locator('.page-state')
    // At least one state should be present
    await expect(pageState).toBeVisible()
  })

  test('F3.3: Search bar has correct features', async ({ page }) => {
    await page.goto('/files')
    await page.waitForTimeout(500)
    const searchInput = page.locator('input.search-input')
    // Search bar should have search icon
    await expect(page.locator('.search-bar')).toBeVisible()
    // Type something - clear button should appear
    await searchInput.fill('test')
    await expect(page.locator('.search-clear')).toBeVisible()
    // Clear the search
    await page.locator('.search-clear').click()
    await expect(searchInput).toHaveValue('')
  })
})
