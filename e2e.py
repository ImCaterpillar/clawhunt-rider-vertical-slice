# -*- coding: utf-8 -*-
"""Playwright browser E2E against the local demo. Server must be running."""
import sys
from playwright.sync_api import sync_playwright, expect

BASE='http://127.0.0.1:8765'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":390,"height":844})
    errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    page.goto(BASE,wait_until='networkidle')
    assert page.get_by_role('heading',name='报名与站点预约').is_visible()
    page.get_by_role('button',name='开始报名').click()
    assert '请先勾选' in page.locator('#status').inner_text()
    page.locator('#consent').check()
    page.get_by_role('button',name='开始报名').click()
    page.get_by_role('textbox',name='演示报名信息').fill('name=Chen birth_ym=1998-05 area=Haidian')
    page.get_by_role('button',name='提交信息').click()
    expect(page.locator('#progress')).to_have_text('3/7',timeout=5000)
    page.get_by_role('textbox',name='演示报名信息').fill('job_type=fulltime has_ebike=yes start_date=soon experience=2years')
    page.get_by_role('button',name='提交信息').click()
    expect(page.locator('#progress')).to_have_text('7/7',timeout=5000)
    page.get_by_role('button',name='预约演示名额').click()
    expect(page.locator('#status')).to_contain_text('预约成功',timeout=5000)
    page.get_by_role('button',name='撤回并清除').click()
    expect(page.locator('#status')).to_contain_text('已撤回',timeout=5000)
    expect(page.locator('#progress')).to_have_text('0/7',timeout=5000)
    page.screenshot(path='e2e-mobile.png',full_page=True)
    assert not errors,errors
    print('PASS: consent gate, 7/7 flow, booking, revoke/clear; viewport 390x844; no page errors')
    browser.close()
