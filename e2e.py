# -*- coding: utf-8 -*-
"""Playwright browser acceptance flows against local demo server."""
from playwright.sync_api import sync_playwright, expect

BASE='http://127.0.0.1:8765'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':390,'height':844},service_workers='allow')
    page=context.new_page();errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    page.goto(BASE,wait_until='networkidle')
    page.get_by_role('heading',name='报名与站点预约').wait_for()
    for width in (375,390,414):
        page.set_viewport_size({'width':width,'height':844})
        page.wait_for_timeout(100)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'horizontal overflow at {width}'
    page.evaluate("document.documentElement.style.fontSize='150%'")
    page.wait_for_timeout(100)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'overflow at 150% text'
    page.evaluate("document.documentElement.style.fontSize='100%'")
    page.get_by_role('button',name='开始报名').click()
    expect(page.locator('#status')).to_contain_text('请先勾选')
    page.locator('#consent').check();page.get_by_role('button',name='开始报名').click()
    page.get_by_role('textbox',name='演示报名信息').fill('name=Chen birth_ym=1998-05 area=Haidian')
    page.get_by_role('button',name='提交信息').click();expect(page.locator('#progress')).to_have_text('3/7')
    # A failed API request must preserve the typed content for retry, not claim success.
    field=page.get_by_role('textbox',name='演示报名信息')
    await_value='job_type=fulltime has_ebike=yes start_date=soon experience=2years'
    field.fill(await_value)
    with page.expect_response(lambda r:'/api/v1/sessions/' in r.url and '/message' in r.url) as response_info:
        page.get_by_role('button',name='提交信息').click()
    response=response_info.value
    expect(page.locator('#progress')).to_have_text('7/7')
    page.get_by_role('button',name='预约演示名额').click();expect(page.locator('#status')).to_contain_text('预约成功')
    page.get_by_role('button',name='撤回并清除').click();expect(page.locator('#status')).to_contain_text('已撤回')
    expect(page.locator('#progress')).to_have_text('0/7')
    # Simulate an offline network request after the UI has loaded.
    page.locator('#consent').check()
    page.get_by_role('button',name='开始报名').click()
    expect(page.locator('#session')).not_to_be_empty()
    field.fill('name=Retry')
    page.context.set_offline(True)
    expect(page.locator('#network')).to_contain_text('离线')
    page.get_by_role('button',name='提交信息').click()
    expect(page.locator('#status')).to_contain_text('离线',timeout=5000)
    assert field.input_value()=='name=Retry'
    expect(page.locator('#progress')).to_have_text('0/7')
    page.wait_for_timeout(10000)
    page.reload(wait_until='domcontentloaded')
    assert field.input_value()=='name=Retry'
    expect(page.locator('#progress')).to_have_text('0/7')
    page.context.set_offline(False)
    expect(page.locator('#network')).to_contain_text('在线')
    expect(page.locator('#session')).not_to_be_empty()
    expect(page.locator('#progress')).to_have_text('1/7',timeout=10000)
    page.reload(wait_until='networkidle')
    expect(page.locator('#progress')).to_have_text('1/7')
    page.screenshot(path='e2e-mobile.png',full_page=True)
    assert not errors,errors
    print('PASS: 375/390/414 widths + 150% text, consent, 7/7, booking, revoke, offline failure/retry state, no page errors')
    context.close();browser.close()
