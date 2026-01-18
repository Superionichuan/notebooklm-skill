#!/usr/bin/env python3
"""
NotebookLM 自动化脚本
通过 Playwright 浏览器自动化与 Google NotebookLM 交互
"""

import argparse
import asyncio
import platform
import sys
import fcntl
import time
from pathlib import Path
from typing import Optional

# 全局锁文件
NLM_LOCK_FILE = Path("/tmp/nlm_global.lock")

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
except ImportError:
    print("请先安装 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


# 配置
NOTEBOOKLM_URL = "https://notebooklm.google.com"

# Profile 路径选项
SKILL_DIR = Path.home() / ".claude" / "skills" / "notebooklm"
ISOLATED_CHROME_PROFILE = SKILL_DIR / "chrome_profile"
ISOLATED_WEBKIT_PROFILE = SKILL_DIR / "webkit_profile"
ISOLATED_FIREFOX_PROFILE = SKILL_DIR / "firefox_profile"

# 多实例 Profile 目录 - 支持多窗口并行运作
MULTI_INSTANCE_PROFILES_DIR = SKILL_DIR / "profiles"


def get_instance_profile(instance_name: str, browser_type: str = "chrome") -> Path:
    """
    获取指定实例的 Profile 路径

    Args:
        instance_name: 实例名称（如 "notebook_01", "notebook_02"）
        browser_type: 浏览器类型

    Returns:
        Profile 目录路径
    """
    profile_dir = MULTI_INSTANCE_PROFILES_DIR / instance_name / browser_type
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def notebook_to_instance(notebook_name: str) -> str:
    """
    根据笔记本名称自动生成实例名称

    每个笔记本自动对应独立实例，确保多窗口操作不同笔记本时互不干扰

    Args:
        notebook_name: 笔记本名称

    Returns:
        实例名称（安全的目录名）
    """
    import hashlib
    import re

    # 提取笔记本名称的前缀（如 "01", "02"）
    prefix_match = re.match(r'^(\d+)[.\s]', notebook_name)
    if prefix_match:
        prefix = f"nb_{prefix_match.group(1)}"
    else:
        # 使用名称的 hash 前8位
        name_hash = hashlib.md5(notebook_name.encode()).hexdigest()[:8]
        prefix = f"nb_{name_hash}"

    return prefix


def auto_init_instance_profile(instance_name: str, browser_type: str = "chrome") -> Path:
    """
    自动初始化实例 Profile

    如果实例 Profile 不存在，自动从默认 Profile 复制

    Args:
        instance_name: 实例名称
        browser_type: 浏览器类型

    Returns:
        Profile 目录路径
    """
    import shutil

    profile_dir = MULTI_INSTANCE_PROFILES_DIR / instance_name / browser_type

    # 如果 Profile 不存在或为空，从默认 Profile 复制
    if not profile_dir.exists() or not any(profile_dir.iterdir()):
        profile_dir.mkdir(parents=True, exist_ok=True)

        # 选择源 Profile
        if browser_type == "chrome":
            source_profile = ISOLATED_CHROME_PROFILE
        elif browser_type in ("safari", "webkit"):
            source_profile = ISOLATED_WEBKIT_PROFILE
        else:
            source_profile = ISOLATED_FIREFOX_PROFILE

        # 复制源 Profile（如果存在）
        if source_profile.exists() and any(source_profile.iterdir()):
            for item in source_profile.iterdir():
                dest = profile_dir / item.name
                if item.is_dir():
                    if not dest.exists():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    if not dest.exists():
                        shutil.copy2(item, dest)

    return profile_dir

# 跨平台 Chrome 路径检测
def get_chrome_path() -> Optional[str]:
    """获取 Chrome 可执行文件路径，如果不存在则返回 None（使用 Playwright 内置 Chromium）"""
    system = platform.system()

    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    elif system == "Windows":
        paths = [
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        ]
    else:  # Linux
        paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]

    for p in paths:
        if Path(p).exists():
            return str(p)
    return None  # 使用 Playwright 内置 Chromium

def get_user_chrome_profile() -> Path:
    """获取用户 Chrome Profile 路径"""
    system = platform.system()

    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    elif system == "Windows":
        return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    else:  # Linux
        return Path.home() / ".config" / "google-chrome"

CHROME_PATH = get_chrome_path()
USER_CHROME_PROFILE = get_user_chrome_profile()


class NotebookLMAutomation:
    def __init__(self, headless: bool = False, use_user_profile: bool = False,
                 browser_type: str = "chrome", instance: str = None,
                 auto_instance: bool = True, target_notebook: str = None,
                 cdp_url: str = None):
        """
        初始化 NotebookLM 自动化实例

        Args:
            headless: 是否无头模式
            use_user_profile: 是否使用用户默认 Chrome Profile
            browser_type: 浏览器类型 (chrome/safari/webkit/firefox)
            instance: 实例名称，用于多实例并行运作（如 "nb_01", "nb_02"）
                      每个实例使用独立的 Chrome Profile，互不干扰
            auto_instance: 是否根据笔记本名称自动分配实例（默认开启）
                          开启后，每个笔记本自动使用独立 Profile，多窗口互不干扰
            target_notebook: 目标笔记本名称（用于自动实例分配）
            cdp_url: CDP 连接 URL (用于连接已运行的 Chrome)
        """
        self.headless = headless
        self.use_user_profile = use_user_profile
        self.browser_type = browser_type.lower()
        self.auto_instance = auto_instance
        self.target_notebook = target_notebook
        self.cdp_url = cdp_url

        # 自动实例分配：根据笔记本名称自动生成实例
        if instance:
            self.instance = instance
        elif auto_instance and target_notebook:
            self.instance = notebook_to_instance(target_notebook)
        else:
            self.instance = None

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def _clear_singleton_locks(self, profile_dir: Path):
        """清除 Chrome Profile 的 SingletonLock 文件，避免冲突"""
        try:
            import glob
            lock_patterns = [
                profile_dir / "SingletonLock",
                profile_dir / "SingletonSocket",
                profile_dir / "SingletonCookie",
            ]
            for pattern in lock_patterns:
                if pattern.exists():
                    pattern.unlink()
            # 也清除可能存在的通配符匹配
            for lock_file in glob.glob(str(profile_dir / "Singleton*")):
                try:
                    Path(lock_file).unlink()
                except:
                    pass
        except Exception as e:
            pass  # 静默处理，锁文件可能不存在

    def _acquire_lock(self, timeout: int = 30):
        """获取全局锁，防止多个 nlm 实例同时运行

        快速失败模式：最多等待 30 秒，超时则退出程序（而不是强制获取锁）
        """
        NLM_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(NLM_LOCK_FILE, 'w')

        start_time = time.time()
        while True:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return  # 成功获取锁
            except (IOError, OSError):
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    print("❌ 另一个 nlm 实例正在运行，请稍后再试")
                    print("   提示: 等待当前操作完成后再执行")
                    self._lock_file.close()
                    import sys
                    sys.exit(1)  # 快速失败，不强制获取锁
                print(f"⏳ 另一个 nlm 实例正在运行，等待中... ({int(elapsed)}s)")
                time.sleep(2)

    def _release_lock(self):
        """释放全局锁"""
        if hasattr(self, '_lock_file') and self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except:
                pass

    def start(self):
        """启动浏览器并初始化页面"""
        # 获取全局锁，防止多个实例同时运行
        self._acquire_lock()

        self.playwright = sync_playwright().start()

        # 根据浏览器类型选择引擎和 Profile
        if self.browser_type == "safari" or self.browser_type == "webkit":
            # Safari/WebKit - 不会和 Chrome 冲突！
            user_data_dir = ISOLATED_WEBKIT_PROFILE
            user_data_dir.mkdir(parents=True, exist_ok=True)
            print(f"🌐 使用 Safari/WebKit 引擎")
            print(f"📁 Profile: {user_data_dir}")

            self.context = self.playwright.webkit.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
            )

        elif self.browser_type == "firefox":
            # Firefox - 不会和 Chrome 冲突！
            user_data_dir = ISOLATED_FIREFOX_PROFILE
            user_data_dir.mkdir(parents=True, exist_ok=True)
            print(f"🦊 使用 Firefox 引擎")
            print(f"📁 Profile: {user_data_dir}")

            self.context = self.playwright.firefox.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 800},
            )

        else:
            # Chrome/Chromium（默认）
            if self.use_user_profile:
                user_data_dir = USER_CHROME_PROFILE
                print(f"🔵 使用你的默认 Chrome Profile")
                print(f"⚠️  请确保关闭其他 Chrome 窗口，否则可能冲突")
            elif self.instance:
                # 多实例模式：每个实例使用独立 Profile
                # 自动初始化 Profile（如果不存在，从默认 Profile 复制）
                user_data_dir = auto_init_instance_profile(self.instance, "chrome")
                self._clear_singleton_locks(user_data_dir)
                if self.auto_instance and self.target_notebook:
                    print(f"🔷 自动实例: {self.instance} (笔记本: {self.target_notebook[:30]}...)")
                else:
                    print(f"🔷 多实例模式: {self.instance}")
                print(f"📁 独立 Profile: {user_data_dir}")
            else:
                user_data_dir = ISOLATED_CHROME_PROFILE
                user_data_dir.mkdir(parents=True, exist_ok=True)
                # 自动清除 SingletonLock，避免 "profile is in use" 错误
                self._clear_singleton_locks(user_data_dir)
                if CHROME_PATH:
                    print(f"🔵 使用隔离 Chrome Profile")
                else:
                    print(f"🔵 使用 Playwright 内置 Chromium")
                print(f"📁 Profile: {user_data_dir}")

            # 构建启动参数
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ]

            # Linux 上需要禁用沙箱
            if platform.system() == "Linux":
                browser_args.extend([
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ])

            launch_args = {
                "user_data_dir": str(user_data_dir),
                "headless": self.headless,
                "args": browser_args,
                "viewport": {"width": 1280, "height": 800},
            }

            # 如果有本地 Chrome，使用它；否则使用 Playwright 内置 Chromium
            if CHROME_PATH:
                launch_args["executable_path"] = CHROME_PATH

            # 如果提供了 CDP URL，通过 CDP 连接已运行的 Chrome
            if self.cdp_url:
                print(f"🔗 通过 CDP 连接: {self.cdp_url}")
                self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)
                self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            else:
                self.context = self.playwright.chromium.launch_persistent_context(**launch_args)

        # 获取或创建页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        # 设置更长的超时时间
        self.page.set_default_timeout(120000)

    def close(self):
        """关闭浏览器"""
        # CDP 模式下不关闭浏览器（保持 Chrome 运行供下次使用）
        if self.cdp_url:
            # 只关闭 context，不关闭 browser
            pass
        elif self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        # 释放全局锁
        self._release_lock()

    def ensure_logged_in(self) -> bool:
        """确保已登录 Google 账号"""
        print("正在打开 NotebookLM...")
        self.page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")

        # 等待页面基本加载
        self.page.wait_for_timeout(5000)

        # 检查是否在登录页面
        current_url = self.page.url
        print(f"当前 URL: {current_url}")

        if "accounts.google.com" in current_url:
            # 检查是否是"请选择账号"页面（多账号选择）
            print("检测到 Google 账号页面，尝试自动选择账号...")
            try:
                # 使用 Playwright 原生点击（模拟真实鼠标事件）
                account_selectors = [
                    '[data-email]',
                    '[data-identifier]',
                    'div[data-authuser]',
                    'li[data-authuser]',
                    '.JDAKTe',  # Google 账号列表项
                ]

                clicked = False
                for selector in account_selectors:
                    try:
                        element = self.page.locator(selector).first
                        if element.count() > 0:
                            print(f"找到账号元素: {selector}")
                            element.click(force=True)
                            clicked = True
                            break
                    except:
                        continue

                if not clicked:
                    # 备用方案：通过文本查找
                    email_locator = self.page.locator('text=@gmail.com').first
                    if email_locator.count() > 0:
                        print("通过 email 文本找到账号")
                        email_locator.click(force=True)
                        clicked = True

                if clicked:
                    print("已点击账号，等待跳转...")
                    self.page.wait_for_timeout(5000)

                    # 再次检查 URL
                    current_url = self.page.url
                    if "notebooklm.google.com" in current_url:
                        print("已自动选择账号并登录")
                        return True

                    # 检查是否出现"验证身份"页面
                    page_text = self.page.inner_text('body')
                    if '验证身份' in page_text or 'Verify' in page_text:
                        # 尝试点击"下一步"按钮
                        next_btn = self.page.locator('button:has-text("下一步"), button:has-text("Next")').first
                        if next_btn.count() > 0:
                            print("检测到验证身份页面，点击下一步...")
                            next_btn.click(force=True)
                            self.page.wait_for_timeout(3000)

                    if "accounts.google.com" not in self.page.url:
                        print(f"登录进行中... 当前: {self.page.url}")
                        self.page.wait_for_timeout(3000)
                        if "notebooklm.google.com" in self.page.url:
                            return True
                else:
                    print("未找到可点击的账号元素")
            except Exception as e:
                print(f"自动选择账号失败: {e}")

            print("\n" + "="*60)
            print("请在浏览器中登录你的 Google 账号")
            print("登录完成后，页面会自动跳转到 NotebookLM")
            print("脚本会自动检测并继续...")
            print("="*60 + "\n")

            # 等待用户登录（最多10分钟）
            try:
                self.page.wait_for_url(
                    lambda url: "notebooklm.google.com" in url and "accounts.google.com" not in url,
                    timeout=600000
                )
                print("\n登录成功！浏览器状态已自动保存。")
                self.page.wait_for_timeout(3000)
            except Exception as e:
                print(f"登录超时或出错: {e}")
                return False
        else:
            print("已登录状态")

        return True

    def list_notebooks(self) -> list:
        """列出所有笔记本"""
        if not self.ensure_logged_in():
            return []

        # 等待页面加载
        self.page.wait_for_timeout(5000)

        notebooks = []
        try:
            # 尝试多种选择器 - NotebookLM 的笔记本卡片
            selectors = [
                'a[href*="/notebook/"]',
                '[data-notebook-id]',
                '.notebook-card',
            ]

            for selector in selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    print(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                    for element in elements:
                        try:
                            title = element.inner_text()
                            if title.strip():
                                # 提取第一行作为标题
                                first_line = title.strip().split('\n')[0]
                                # 过滤掉按钮文字
                                if first_line not in ['more_vert', 'add', '新建', '新建笔记本', 'settings', '设置']:
                                    notebooks.append(first_line)
                        except:
                            pass
                    if notebooks:
                        break

            # 如果选择器都没匹配，从页面文本解析笔记本名称
            if not notebooks:
                try:
                    main_text = self.page.inner_text('body')
                    lines = main_text.split('\n')

                    # 查找包含日期格式的行（笔记本名称后面通常跟着日期）
                    import re
                    for i, line in enumerate(lines):
                        line = line.strip()
                        # 匹配日期格式：2025年4月23日 或类似
                        if re.search(r'\d{4}年\d{1,2}月\d{1,2}日', line):
                            # 前一行可能是笔记本名称
                            if i > 0:
                                prev_line = lines[i-1].strip()
                                # 过滤掉无效内容
                                skip_words = ['more_vert', 'add', '新建', 'settings', '设置',
                                            'public', 'chevron_right', '查看全部', 'grid_view',
                                            'view_headline', 'PRO', '全部', '精选笔记本',
                                            '最近打开过的笔记本', '最近', 'arrow_drop_down']
                                if prev_line and prev_line not in skip_words and len(prev_line) > 2:
                                    if prev_line not in notebooks:
                                        notebooks.append(prev_line)
                except Exception as e:
                    print(f"解析页面内容时出错: {e}")

            # 如果还是没找到，保存截图供调试
            if not notebooks:
                screenshot_path = SKILL_DIR / "debug_screenshot.png"
                self.page.screenshot(path=str(screenshot_path))
                print(f"\n调试截图已保存: {screenshot_path}")

        except Exception as e:
            print(f"获取笔记本列表时出错: {e}")

        return notebooks

    def create_notebook(self, name: str) -> bool:
        """创建新笔记本"""
        if not self.ensure_logged_in():
            return False

        try:
            # 点击创建按钮
            create_selectors = [
                'button:has-text("New notebook")',
                'button:has-text("Create")',
                'button:has-text("新建")',
                '[aria-label*="Create"]',
                '[aria-label*="New"]',
                'button:has-text("+")',
            ]

            for selector in create_selectors:
                button = self.page.query_selector(selector)
                if button:
                    print(f"点击创建按钮: {selector}")
                    button.click()
                    self.page.wait_for_timeout(2000)
                    break
            else:
                print("未找到创建按钮")
                return False

            # 等待并输入名称
            self.page.wait_for_timeout(1000)
            name_input = self.page.query_selector('input[type="text"], textarea')
            if name_input:
                name_input.fill(name)
                self.page.wait_for_timeout(500)

            # 确认
            confirm_selectors = [
                'button:has-text("Create")',
                'button:has-text("确认")',
                'button:has-text("OK")',
                'button[type="submit"]',
            ]

            for selector in confirm_selectors:
                button = self.page.query_selector(selector)
                if button:
                    button.click()
                    break

            self.page.wait_for_timeout(2000)
            print(f"笔记本 '{name}' 创建成功")
            return True

        except Exception as e:
            print(f"创建笔记本时出错: {e}")
            return False

    def open_notebook(self, notebook_name: str) -> bool:
        """打开指定笔记本"""
        if not self.ensure_logged_in():
            return False

        try:
            # 先回到主页
            self.page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")
            self.page.wait_for_timeout(5000)

            # 查找并点击笔记本 - 尝试多种策略
            notebook = None

            # 策略1: 精确匹配
            notebook = self.page.query_selector(f'text="{notebook_name}"')

            # 策略2: 包含匹配（用于长名称）
            if not notebook or not notebook.is_visible():
                # 截取名称的前30个字符进行匹配
                short_name = notebook_name[:30] if len(notebook_name) > 30 else notebook_name
                notebook = self.page.query_selector(f'text=/{short_name}/')

            # 策略3: 通过链接查找
            if not notebook or not notebook.is_visible():
                links = self.page.query_selector_all('a[href*="/notebook/"]')
                for link in links:
                    try:
                        text = link.inner_text()
                        if notebook_name in text or text in notebook_name:
                            notebook = link
                            break
                    except:
                        pass

            if notebook and notebook.is_visible():
                # 使用 force=True 跳过可操作性检查，因为可能有覆盖层
                notebook.click(force=True)
                self.page.wait_for_timeout(5000)
                print(f"已打开笔记本: {notebook_name}")
                return True
            else:
                print(f"未找到笔记本: {notebook_name}")
                # 保存截图供调试
                screenshot_path = SKILL_DIR / "debug_open_notebook.png"
                self.page.screenshot(path=str(screenshot_path))
                print(f"调试截图已保存: {screenshot_path}")
                return False
        except Exception as e:
            print(f"打开笔记本时出错: {e}")
            return False

    def upload_document(self, file_path: str, notebook_name: Optional[str] = None) -> bool:
        """上传文档到笔记本"""
        file_path = Path(file_path).expanduser().resolve()

        if not file_path.exists():
            print(f"文件不存在: {file_path}")
            return False

        # 如果指定了笔记本，先打开它
        if notebook_name:
            if not self.open_notebook(notebook_name):
                print(f"创建新笔记本: {notebook_name}")
                self.create_notebook(notebook_name)
                self.page.wait_for_timeout(2000)

        try:
            # 查找文件上传输入框
            file_input = self.page.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(str(file_path))
                self.page.wait_for_timeout(3000)
                print(f"文件 '{file_path.name}' 上传成功")
                return True

            # 尝试点击上传按钮
            upload_selectors = [
                'button:has-text("Upload")',
                'button:has-text("Add source")',
                'button:has-text("上传")',
                'button:has-text("添加来源")',
                '[aria-label*="Upload"]',
                '[aria-label*="Add"]',
            ]

            for selector in upload_selectors:
                button = self.page.query_selector(selector)
                if button:
                    button.click()
                    self.page.wait_for_timeout(1000)

                    # 再次查找文件输入框
                    file_input = self.page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(str(file_path))
                        self.page.wait_for_timeout(3000)
                        print(f"文件 '{file_path.name}' 上传成功")
                        return True

            print("未找到上传入口")
            return False

        except Exception as e:
            print(f"上传文档时出错: {e}")
            return False

    def generate_audio(self, notebook_name: str, output_path: Optional[str] = None) -> bool:
        """生成播客音频 (Audio Overview)"""
        if not self.open_notebook(notebook_name):
            return False

        try:
            # 查找 Audio Overview 按钮
            audio_selectors = [
                'button:has-text("Audio Overview")',
                'button:has-text("Generate audio")',
                'button:has-text("音频概述")',
                '[aria-label*="Audio"]',
            ]

            for selector in audio_selectors:
                button = self.page.query_selector(selector)
                if button:
                    button.click()
                    self.page.wait_for_timeout(2000)
                    break
            else:
                print("未找到 Audio Overview 按钮")
                return False

            # 点击生成
            generate_button = self.page.query_selector(
                'button:has-text("Generate"), button:has-text("生成")'
            )
            if generate_button:
                generate_button.click()

            print("音频生成已开始，这可能需要几分钟...")

            # 等待下载按钮
            for i in range(120):  # 最多等待10分钟
                download_button = self.page.query_selector(
                    'button:has-text("Download"), a[download], [aria-label*="Download"]'
                )
                if download_button:
                    if output_path:
                        with self.page.expect_download() as download_info:
                            download_button.click()
                        download = download_info.value
                        download.save_as(output_path)
                        print(f"音频已保存到: {output_path}")
                    else:
                        download_button.click()
                        print("音频下载已开始")
                    return True

                self.page.wait_for_timeout(5000)
                if i % 12 == 0:
                    print(f"等待中... ({i * 5} 秒)")

            print("等待音频生成超时")
            return False

        except Exception as e:
            print(f"生成音频时出错: {e}")
            return False

    def chat(self, notebook_name: str, question: str) -> str:
        """与笔记本对话"""
        if not self.open_notebook(notebook_name):
            return ""

        try:
            # 查找聊天输入框
            input_selectors = [
                'textarea',
                'input[type="text"]',
                '[contenteditable="true"]',
                '[role="textbox"]',
            ]

            chat_input = None
            for selector in input_selectors:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    if el.is_visible():
                        chat_input = el
                        break
                if chat_input:
                    break

            if not chat_input:
                print("未找到聊天输入框")
                return ""

            # 输入问题
            chat_input.fill(question)
            self.page.wait_for_timeout(500)

            # 发送
            chat_input.press("Enter")
            self.page.wait_for_timeout(5000)

            # 等待回复加载
            self.page.wait_for_timeout(8000)

            # 获取回复
            response_selectors = [
                '[data-message]',
                '.response',
                '.answer',
                '[role="article"]',
            ]

            for selector in response_selectors:
                responses = self.page.query_selector_all(selector)
                if responses:
                    last = responses[-1]
                    return last.inner_text().strip()

            return ""

        except Exception as e:
            print(f"对话时出错: {e}")
            return ""

    def delete_notebook(self, notebook_name: str) -> bool:
        """删除笔记本"""
        if not self.ensure_logged_in():
            return False

        try:
            notebook = self.page.query_selector(f'text="{notebook_name}"')
            if not notebook:
                print(f"未找到笔记本: {notebook_name}")
                return False

            # 右键菜单
            notebook.click(button="right")
            self.page.wait_for_timeout(1000)

            # 点击删除
            delete = self.page.query_selector('text="Delete", text="删除"')
            if delete:
                delete.click()
                self.page.wait_for_timeout(1000)

                # 确认
                confirm = self.page.query_selector(
                    'button:has-text("Delete"), button:has-text("确认")'
                )
                if confirm:
                    confirm.click()

                self.page.wait_for_timeout(2000)
                print(f"笔记本 '{notebook_name}' 已删除")
                return True

            return False

        except Exception as e:
            print(f"删除笔记本时出错: {e}")
            return False

    def list_sources(self, notebook_name: str) -> list:
        """列出笔记本中的所有源"""
        if not self.open_notebook(notebook_name):
            return []

        sources = []
        try:
            self.page.wait_for_timeout(3000)

            # UI 元素过滤列表 - 这些不是真正的源
            ui_elements = [
                'add', 'more_vert', 'search', 'close', 'arrow', 'keyboard',
                'thumb_up', 'thumb_down', 'check', 'edit', 'delete', 'remove',
                'language', 'drive_pdf', 'web', 'youtube', 'link', 'article',
                'markdown', 'pdf', 'folder', 'settings', 'menu', 'expand',
                '🔎', '➕', '✓', '✕', '⋮',
                'Sources', '来源', 'Add source', '添加来源', 'Notes', '笔记',
                'Studio', 'Chat', '聊天', 'Deep Research', '获取深度报告',
                '新来源', 'PRO', '全部', 'All', 'Select all', '全选',
            ]

            # UI 提示语过滤 - 包含这些关键词的整行都过滤掉
            ui_prompts = [
                '试用', '获取深度报告', '新来源', 'Try', 'Get deep',
            ]

            # NotebookLM 源通常在左侧面板
            # 尝试多种选择器定位源列表
            source_selectors = [
                '[data-source-id]',
                '.source-item',
                '[role="listitem"]',
                'div[class*="source"]',
                'button[class*="source"]',
            ]

            for selector in source_selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        try:
                            text = el.inner_text().strip()
                            if text and len(text) > 2:
                                # 提取第一行作为源名称
                                first_line = text.split('\n')[0].strip()
                                # 过滤 UI 元素
                                if first_line and first_line not in sources:
                                    # 检查是否是 UI 元素
                                    is_ui = False
                                    for ui in ui_elements:
                                        if first_line.lower() == ui.lower() or first_line == ui:
                                            is_ui = True
                                            break
                                    # 检查是否包含 UI 提示语
                                    if not is_ui:
                                        for prompt in ui_prompts:
                                            if prompt.lower() in first_line.lower():
                                                is_ui = True
                                                break
                                    # 过滤太短的（通常是图标文字）
                                    if not is_ui and len(first_line) > 5:
                                        sources.append(first_line)
                        except:
                            pass
                    if sources:
                        break

            # 备用方法：从页面左侧面板解析
            if not sources:
                try:
                    # 查找左侧面板
                    left_panel = self.page.query_selector('aside, [role="navigation"], div[class*="sidebar"], div[class*="panel"]')
                    if left_panel:
                        panel_text = left_panel.inner_text()
                        lines = panel_text.split('\n')
                        for line in lines:
                            line = line.strip()
                            # 过滤 UI 元素
                            if not line or len(line) <= 5:
                                continue

                            is_ui = False
                            for ui in ui_elements:
                                if line.lower() == ui.lower() or line == ui:
                                    is_ui = True
                                    break
                                # 也检查是否以 UI 元素开头
                                if line.lower().startswith(ui.lower() + ' '):
                                    is_ui = True
                                    break

                            # 检查是否包含 UI 提示语
                            if not is_ui:
                                for prompt in ui_prompts:
                                    if prompt.lower() in line.lower():
                                        is_ui = True
                                        break

                            if not is_ui and line not in sources:
                                # 检查是否像是文件名/标题模式
                                if ('.' in line or '-' in line or len(line) > 15 or
                                    any(ext in line.lower() for ext in ['.pdf', '.docx', '.txt', '.md'])):
                                    sources.append(line)
                except Exception as e:
                    print(f"解析左侧面板时出错: {e}")

            # 保存截图供调试
            if not sources:
                screenshot_path = SKILL_DIR / "debug_sources.png"
                self.page.screenshot(path=str(screenshot_path))
                print(f"调试截图已保存: {screenshot_path}")
                print("提示: 请查看截图确认源面板结构")

        except Exception as e:
            print(f"列出源时出错: {e}")

        return sources

    def detect_mode(self) -> str:
        """检测当前 UI 模式: 'chat', 'source_search', 'unknown'"""
        try:
            # 检查源搜索输入框是否活跃
            source_search = self.page.query_selector('textarea[placeholder*="搜索新来源"], input[placeholder*="搜索新来源"]')
            chat_input = self.page.query_selector('textarea[placeholder*="开始输入"], textarea[aria-label="查询框"]')

            if source_search and source_search.is_visible():
                return 'source_search'
            elif chat_input and chat_input.is_visible():
                return 'chat'
            return 'unknown'
        except:
            return 'unknown'

    def detect_search_state(self) -> str:
        """
        检测搜索状态机状态

        Returns:
            'READY' - 搜索框可用，可以进行新搜索
            'PENDING_RESULTS' - 有待处理的搜索结果（查看按钮可见）
            'UNKNOWN' - 未知状态
        """
        try:
            # 检查是否有待处理的搜索结果（查看按钮可见）
            view_btn = self.page.query_selector('button:has-text("查看")')
            if view_btn and view_btn.is_visible():
                return 'PENDING_RESULTS'

            # 检查搜索框是否可用
            search_selectors = [
                'textarea[aria-label="基于输入的查询发现来源"]',
                'textarea[placeholder*="在网络中搜索新来源"]',
            ]

            for sel in search_selectors:
                search_input = self.page.query_selector(sel)
                if search_input and search_input.is_visible():
                    return 'READY'

            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def select_source_type(self, source_type: str = "web") -> bool:
        """
        选择来源类型

        Args:
            source_type: "web", "drive", "youtube", "link"

        Returns:
            是否成功选择
        """
        try:
            # 查找来源类型选择器按钮（显示 "language" 图标）
            type_btn_selectors = [
                'button:has-text("language")',
                'button:has(span:text("language"))',
                '[aria-label*="来源类型"]',
                '[aria-label*="source type"]',
            ]

            type_btn = None
            for sel in type_btn_selectors:
                type_btn = self.page.query_selector(sel)
                if type_btn and type_btn.is_visible():
                    break

            if not type_btn:
                print("未找到来源类型选择器")
                return False

            type_btn.click()
            self.page.wait_for_timeout(1000)

            # 根据类型选择对应选项
            type_map = {
                "web": ["网页", "Web", "web"],
                "drive": ["Google 云端硬盘", "云端硬盘", "Drive", "Google Drive"],
                "youtube": ["YouTube", "youtube"],
                "link": ["链接", "Link", "link"],
            }

            options = type_map.get(source_type.lower(), type_map["web"])

            for option_text in options:
                option = self.page.query_selector(f'text="{option_text}"')
                if option and option.is_visible():
                    option.click()
                    self.page.wait_for_timeout(500)
                    print(f"已选择来源类型: {source_type}")
                    return True

            # 备用方法：按 Escape 关闭菜单
            self.page.keyboard.press("Escape")
            print(f"未找到来源类型选项: {source_type}")
            return False

        except Exception as e:
            print(f"选择来源类型时出错: {e}")
            return False

    def select_research_mode(self, mode: str = "fast") -> bool:
        """
        选择研究模式

        Args:
            mode: "fast" (快速研究) 或 "deep" (深度研究)

        Returns:
            是否成功选择
        """
        try:
            # 查找研究模式选择器按钮（显示 "search_spark" 图标）
            mode_btn_selectors = [
                'button:has-text("search_spark")',
                'button:has(span:text("search_spark"))',
                '[aria-label*="研究模式"]',
                '[aria-label*="research mode"]',
            ]

            mode_btn = None
            for sel in mode_btn_selectors:
                mode_btn = self.page.query_selector(sel)
                if mode_btn and mode_btn.is_visible():
                    break

            if not mode_btn:
                print("未找到研究模式选择器")
                return False

            mode_btn.click()
            self.page.wait_for_timeout(1000)

            # 根据模式选择对应选项
            mode_map = {
                "fast": ["Fast Research", "快速研究", "Fast"],
                "deep": ["Deep Research", "深度研究", "Deep"],
            }

            options = mode_map.get(mode.lower(), mode_map["fast"])

            for option_text in options:
                option = self.page.query_selector(f'text="{option_text}"')
                if option and option.is_visible():
                    option.click()
                    self.page.wait_for_timeout(500)
                    print(f"已选择研究模式: {mode}")
                    return True

            # 备用方法：按 Escape 关闭菜单
            self.page.keyboard.press("Escape")
            print(f"未找到研究模式选项: {mode}")
            return False

        except Exception as e:
            print(f"选择研究模式时出错: {e}")
            return False

    def click_view_results(self) -> bool:
        """
        点击"查看"按钮查看搜索结果

        Returns:
            是否成功点击
        """
        try:
            # 等待搜索完成标志
            completion_selectors = [
                'text="Fast Research 已完成"',
                'text="已完成"',
                'text="completed"',
                '.source-discovery-completed',
            ]

            completed = False
            for sel in completion_selectors:
                el = self.page.query_selector(sel)
                if el and el.is_visible():
                    completed = True
                    break

            if not completed:
                print("搜索尚未完成，等待中...")
                self.page.wait_for_timeout(5000)

            # 查找"查看"按钮
            view_btn_selectors = [
                'button:has-text("查看")',
                'button:has-text("View")',
                'button:has-text("查看结果")',
                '[aria-label*="查看"]',
                '[aria-label*="View"]',
            ]

            for sel in view_btn_selectors:
                view_btn = self.page.query_selector(sel)
                if view_btn and view_btn.is_visible():
                    view_btn.click()
                    self.page.wait_for_timeout(2000)
                    print("已点击查看按钮")
                    return True

            print("未找到查看按钮")
            return False

        except Exception as e:
            print(f"点击查看按钮时出错: {e}")
            return False

    def get_search_results_with_actions(self) -> list:
        """
        获取搜索结果列表及其可用操作

        Returns:
            搜索结果列表，每项包含 {title, can_import, can_remove, source_type}
        """
        results = []
        try:
            # 点击查看后，搜索结果显示在左侧面板的 mat-checkbox 列表中
            # 用 JavaScript 提取结果
            data = self.page.evaluate('''() => {
                const results = [];
                const checkboxes = document.querySelectorAll("mat-checkbox");

                checkboxes.forEach((cb, i) => {
                    // 跳过"选择所有来源"的复选框
                    let container = cb.parentElement;
                    for (let j = 0; j < 5 && container; j++) {
                        const text = container.innerText || "";
                        // 检查是否包含来源类型标识
                        if (text.includes("drive_pdf") || text.includes("web") ||
                            text.includes("youtube") || text.includes("link") ||
                            text.includes("PDF") || text.includes("http")) {

                            // 解析文本，提取标题
                            const lines = text.split("\\n").filter(l => l.trim());
                            let sourceType = "unknown";
                            let title = "";

                            for (const line of lines) {
                                const trimmed = line.trim();
                                if (trimmed === "drive_pdf" || trimmed === "web" ||
                                    trimmed === "youtube" || trimmed === "link") {
                                    sourceType = trimmed;
                                } else if (trimmed.length > 10 && !trimmed.startsWith("选择") &&
                                           !trimmed.includes("来源") && title === "") {
                                    title = trimmed;
                                }
                            }

                            if (title) {
                                results.push({
                                    index: i,
                                    title: title.substring(0, 100),
                                    sourceType: sourceType,
                                    checked: cb.classList.contains("mat-mdc-checkbox-checked")
                                });
                            }
                            break;
                        }
                        container = container.parentElement;
                    }
                });
                return results;
            }''')

            # 检查是否有"添加"按钮（表示可以导入）
            add_btn = self.page.query_selector('button:has-text("添加")')
            can_import = add_btn is not None and add_btn.is_visible()

            for item in data:
                result = {
                    "title": item.get("title", ""),
                    "source_type": item.get("sourceType", "unknown"),
                    "can_import": can_import,
                    "can_remove": True,  # 搜索结果都可以移除
                    "checked": item.get("checked", False),
                    "index": item.get("index", 0)
                }
                results.append(result)

            if not results:
                print("未找到搜索结果，尝试备用方法...")
                # 备用方法：直接从面板文本提取
                panel = self.page.query_selector('.source-panel')
                if panel:
                    text = panel.inner_text()
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if len(line) > 20 and not any(skip in line for skip in
                            ['选择', '来源', '添加', '删除', 'drive_pdf', 'web', 'youtube']):
                            results.append({
                                "title": line[:100],
                                "source_type": "unknown",
                                "can_import": can_import,
                                "can_remove": True
                            })

            return results

        except Exception as e:
            print(f"获取搜索结果时出错: {e}")
            return results

    def _old_get_search_results_with_actions(self) -> list:
        """旧版方法，保留作为参考"""
        results = []
        try:
            container_selectors = [
                '.source-discovery-completed-source-list',
                '[class*="source-discovery-completed"]',
                '.source-discovery-container',
            ]

            container = None
            for sel in container_selectors:
                container = self.page.query_selector(sel)
                if container:
                    break

            if not container:
                print("未找到搜索结果容器")
                return results

            result_items = container.query_selector_all('.shallow-research-title, [class*="source-info"]')

            for item in result_items:
                try:
                    title = item.inner_text().strip()
                    if not title or len(title) < 5:
                        continue

                    parent = item.evaluate_handle("el => el.parentElement")

                    result = {
                        "title": title[:100],
                        "can_import": False,
                        "can_remove": False,
                    }

                    import_btn = self.page.query_selector(f'button:has-text("添加"):near(:text("{title[:30]}"))')
                    remove_btn = self.page.query_selector(f'button:has-text("删除"):near(:text("{title[:30]}"))')

                    if import_btn:
                        result["can_import"] = True
                    if remove_btn:
                        result["can_remove"] = True

                    results.append(result)
                except:
                    pass

            print(f"找到 {len(results)} 个搜索结果")
            return results

        except Exception as e:
            print(f"获取搜索结果时出错: {e}")
            return results

    def import_search_result(self, title: str) -> bool:
        """
        导入指定的搜索结果

        Args:
            title: 结果标题（部分匹配）

        Returns:
            是否成功导入
        """
        try:
            # 先找到结果项
            result_el = self.page.query_selector(f'text="{title[:50]}"')
            if not result_el:
                # 尝试模糊匹配
                result_el = self.page.query_selector(f'text=/{title[:30]}/')

            if not result_el:
                print(f"未找到搜索结果: {title}")
                return False

            # 点击结果项选中它
            result_el.click()
            self.page.wait_for_timeout(500)

            # 查找并点击导入/添加按钮
            import_selectors = [
                'button:has-text("添加")',
                'button:has-text("Add")',
                'button:has-text("导入")',
                'button:has-text("Import")',
                '[aria-label*="添加"]',
                '[aria-label*="Add"]',
            ]

            for sel in import_selectors:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self.page.wait_for_timeout(2000)
                    print(f"已导入: {title[:50]}...")
                    return True

            print("未找到导入按钮")
            return False

        except Exception as e:
            print(f"导入搜索结果时出错: {e}")
            return False

    def remove_search_result(self, title: str) -> bool:
        """
        从搜索结果中移除指定项

        Args:
            title: 结果标题（部分匹配）

        Returns:
            是否成功移除
        """
        try:
            # 先找到结果项
            result_el = self.page.query_selector(f'text="{title[:50]}"')
            if not result_el:
                result_el = self.page.query_selector(f'text=/{title[:30]}/')

            if not result_el:
                print(f"未找到搜索结果: {title}")
                return False

            # 点击结果项选中它
            result_el.click()
            self.page.wait_for_timeout(500)

            # 查找并点击删除/移除按钮
            remove_selectors = [
                'button:has-text("删除")',
                'button:has-text("Remove")',
                'button:has-text("移除")',
                'button:has-text("Delete")',
                '[aria-label*="删除"]',
                '[aria-label*="Remove"]',
            ]

            for sel in remove_selectors:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self.page.wait_for_timeout(1000)
                    print(f"已移除: {title[:50]}...")
                    return True

            print("未找到移除按钮")
            return False

        except Exception as e:
            print(f"移除搜索结果时出错: {e}")
            return False

    def search_sources(self, notebook_name: str, query: str, mode: str = "fast", source_type: str = "web", auto_clear: bool = True, timeout: int = None) -> list:
        """
        搜索新来源（完整工作流程）

        Args:
            notebook_name: 笔记本名称
            query: 搜索查询
            mode: 研究模式 - "fast" (快速研究) 或 "deep" (深度研究)
            source_type: 来源类型 - "web", "drive", "youtube", "link"
            auto_clear: 是否自动清除待处理的搜索结果（默认True）

        Returns:
            搜索结果列表
        """
        if not self.open_notebook(notebook_name):
            return []

        try:
            self.page.wait_for_timeout(3000)

            # 检查搜索状态，处理待处理的结果
            state = self.detect_search_state()
            print(f"搜索状态: {state}")

            if state == 'PENDING_RESULTS':
                if auto_clear:
                    print("检测到待处理的搜索结果，自动清除...")
                    if not self.clear_temp_sources():
                        print("⚠️ 无法清除待处理结果，搜索可能失败")
                    self.page.wait_for_timeout(2000)
                else:
                    print("⚠️ 有待处理的搜索结果，请先使用 clear-search 命令清除")
                    return []

            # 步骤1和2: 选择来源类型和研究模式（仅非默认值时才选择）
            # 默认值 web 和 fast 通常已被选中，跳过以避免超时
            if source_type.lower() != "web":
                self.select_source_type(source_type)
                self.page.wait_for_timeout(500)

            if mode.lower() != "fast":
                self.select_research_mode(mode)
                self.page.wait_for_timeout(500)

            # 找到源搜索输入框 - 使用多种选择器
            search_selectors = [
                'textarea[aria-label="基于输入的查询发现来源"]',
                'textarea[placeholder*="在网络中搜索新来源"]',
                'textarea[aria-label*="发现来源"]',
                'textarea[aria-label*="查询发现"]',
                'textarea[placeholder*="搜索新来源"]',
            ]

            search_input = None
            for sel in search_selectors:
                search_input = self.page.query_selector(sel)
                if search_input and search_input.is_visible():
                    print(f"找到搜索框: {sel}")
                    break

            if not search_input or not search_input.is_visible():
                print("未找到源搜索输入框，尝试点击添加来源按钮...")
                # 尝试点击"添加来源"按钮来触发搜索界面
                add_btn = self.page.query_selector('button:has-text("添加来源"), button:has-text("Add source")')
                if add_btn:
                    add_btn.click()
                    self.page.wait_for_timeout(2000)
                    # 再次查找搜索框
                    for sel in search_selectors:
                        search_input = self.page.query_selector(sel)
                        if search_input and search_input.is_visible():
                            break

                if not search_input:
                    print("仍未找到源搜索输入框")
                    return []

            # 输入搜索查询 - 使用 Playwright 原生方法
            try:
                self.page.wait_for_timeout(1000)

                # 尝试使用 Playwright 的 fill 方法
                search_input.click()
                self.page.wait_for_timeout(500)
                search_input.fill(query)
                self.page.wait_for_timeout(500)

                # 点击提交按钮（箭头按钮）
                submit_btn = self.page.query_selector('button:has-text("arrow_forward"), button[aria-label*="搜索"], button[aria-label*="提交"]')
                if submit_btn and submit_btn.is_visible():
                    print("找到提交按钮，点击...")
                    submit_btn.click()
                else:
                    # 备用方法：按 Enter 键
                    print("未找到提交按钮，按 Enter 键...")
                    search_input.press("Enter")

                print(f"搜索查询已提交: {query}")

            except Exception as click_err:
                print(f"输入搜索时出错: {click_err}")
                # 备用方法：使用 JavaScript
                try:
                    self.page.evaluate(f'''
                        const textarea = document.querySelector('textarea[aria-label="基于输入的查询发现来源"]');
                        if (textarea) {{
                            textarea.value = "{query}";
                            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    ''')
                    self.page.keyboard.press("Enter")
                except:
                    pass

            print(f"正在{'深度' if mode == 'deep' else '快速'}搜索: {query}")

            # 步骤4: 等待搜索完成
            max_wait = 1800 if mode == "deep" else 1200  # deep=30分钟, fast=20分钟
            search_completed = False

            for i in range(max_wait):
                self.page.wait_for_timeout(1000)

                # 检查加载状态
                loading = self.page.query_selector('[class*="loading"], [class*="spinner"]')
                if loading and loading.is_visible():
                    if i % 10 == 0:
                        print(f"正在搜索... ({i}秒)")
                    continue

                # 检查完成指标（按优先级）
                # 1. 查看按钮是最可靠的完成指标
                view_btn = self.page.query_selector('button:has-text("查看")')
                if view_btn and view_btn.is_visible():
                    print(f"搜索完成！(检测到查看按钮, {i}秒)")
                    search_completed = True
                    break

                # 2. 检查完成文本
                completion_texts = [
                    'text="Fast Research 已完成"',
                    'text="Deep Research 已完成"',
                    'text="已完成"',
                ]
                for sel in completion_texts:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        print(f"搜索完成！(检测到: {sel}, {i}秒)")
                        search_completed = True
                        break

                if search_completed:
                    break

                # 3. 检查搜索结果
                results = self.page.query_selector_all('.shallow-research-title')
                if results and len(results) > 0:
                    print(f"搜索完成！(找到 {len(results)} 个结果, {i}秒)")
                    search_completed = True
                    break

                if i % 10 == 0:
                    print(f"等待搜索完成... ({i}/{max_wait}秒)")

            # 步骤5: 搜索完成，提示用户下一步操作
            # 注意：不自动点击"查看"按钮，保持在可清除状态
            # 用户可以选择：
            #   - view-results: 查看并选择导入
            #   - clear-search: 清除所有结果

            # 步骤6: 获取搜索结果数量（从页面文本提取）
            results = []

            # 方法1: 从页面文本中提取URL和标题
            # 搜索结果通常包含 http/https 链接
            try:
                body_text = self.page.inner_text('body')
                lines = body_text.split('\n')

                for line in lines:
                    line = line.strip()
                    # 跳过太短或太长的行
                    if len(line) < 20 or len(line) > 300:
                        continue
                    # 跳过按钮和图标文字
                    skip_words = ['查看', '删除', '导入', 'web', 'drive_pdf', 'youtube', 'link',
                                 'thumb_up', 'thumb_down', 'add', 'remove', 'close', 'arrow',
                                 'keyboard', '添加来源', '创建笔记本', '保存到笔记', 'more_vert']
                    if any(kw in line.lower() for kw in skip_words):
                        continue
                    # 检查是否像是搜索结果标题
                    if ('http' in line.lower() or 'www.' in line.lower() or
                        '...' in line or line.endswith('...') or
                        any(ext in line.lower() for ext in ['.pdf', '.html', '.com', '.org', '.edu'])):
                        if line not in results:
                            results.append(line)
            except:
                pass

            # 方法2: 查找 shallow-research-title 类的元素（搜索结果标题）
            if not results:
                title_elements = self.page.query_selector_all('.shallow-research-title, [class*="shallow-research-title"]')
                if title_elements:
                    print(f"找到 {len(title_elements)} 个搜索结果标题元素")
                    for el in title_elements:
                        try:
                            text = el.inner_text().strip()
                            if text and len(text) > 5 and text not in results:
                                results.append(text)
                        except:
                            pass

            # 方法3: 查找 source-info 类的元素
            if not results:
                source_info_elements = self.page.query_selector_all('.source-info, [class*="source-info"]')
                for el in source_info_elements:
                    try:
                        text = el.inner_text().strip()
                        first_line = text.split('\n')[0].strip()
                        # 去掉可能的前缀
                        for prefix in ['web ', 'drive_pdf ', 'youtube ', 'link ']:
                            if first_line.startswith(prefix):
                                first_line = first_line[len(prefix):]
                        if first_line and len(first_line) > 5 and first_line not in results:
                            results.append(first_line)
                    except:
                        pass

            # 方法4: 从 source-discovery-completed-source-list 容器获取
            if not results:
                container = self.page.query_selector('.source-discovery-completed-source-list, [class*="source-discovery-completed"]')
                if container:
                    text = container.inner_text()
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        # 跳过按钮文字和图标
                        skip_words = ['查看', '删除', '导入', 'web', 'drive_pdf', 'youtube', 'link',
                                     'thumb_up', 'thumb_down', 'add', 'remove', 'close']
                        if line.lower() in skip_words:
                            continue
                        if len(line) > 15 and line not in results:
                            results.append(line)

            # 去重并限制数量
            results = list(dict.fromkeys(results))[:20]

            print(f"找到 {len(results)} 个搜索结果")
            for i, r in enumerate(results[:5]):
                print(f"  {i+1}. {r[:70]}...")
            if len(results) > 5:
                print(f"  ... 还有 {len(results) - 5} 个结果")

            print("\n⚠️  重要：搜索结果是临时的。必须导入或移除结果后才能进行新的搜索！")
            print("使用命令:")
            print("  - import-result --notebook <name> --title <result_title>  导入结果")
            print("  - remove-result --notebook <name> --title <result_title>  移除结果")
            print("  - clear-search --notebook <name>  清除所有临时结果")

            return results

        except Exception as e:
            print(f"搜索源时出错: {e}")
            return []

    def inspect_source(self, source_name: str) -> dict:
        """
        检查/预览源的详细信息

        Args:
            source_name: 源名称

        Returns:
            包含源信息的字典 {title, type, preview, url}
        """
        try:
            # 找到并点击源
            source_el = self.page.query_selector(f'text="{source_name}"')
            if not source_el:
                source_el = self.page.query_selector(f'text=/{source_name[:30]}/')

            if not source_el:
                print(f"未找到源: {source_name}")
                return {}

            source_el.click()
            self.page.wait_for_timeout(2000)

            # 获取源详情
            info = {"title": source_name, "type": "unknown", "preview": "", "url": ""}

            # 尝试获取类型（web, pdf, markdown 等）
            type_el = self.page.query_selector('[class*="source-type"], [data-type]')
            if type_el:
                info["type"] = type_el.inner_text().strip()

            # 尝试获取预览内容
            preview_el = self.page.query_selector('[class*="preview"], [class*="content"], [class*="summary"]')
            if preview_el:
                info["preview"] = preview_el.inner_text()[:500]

            # 尝试获取 URL
            url_el = self.page.query_selector('a[href*="http"]')
            if url_el:
                info["url"] = url_el.get_attribute("href")

            print(f"源信息: {info['title']} ({info['type']})")
            return info

        except Exception as e:
            print(f"检查源时出错: {e}")
            return {}

    def import_temp_source(self, source_name: str) -> bool:
        """将临时源导入到永久源列表"""
        try:
            # 找到临时源并点击导入
            source_el = self.page.query_selector(f'text="{source_name}"')
            if not source_el:
                # 尝试部分匹配
                source_el = self.page.query_selector(f'text=/{source_name[:30]}/')

            if source_el:
                source_el.click()
                self.page.wait_for_timeout(1000)

                # 查找导入/添加按钮
                import_selectors = [
                    'button:has-text("Add")',
                    'button:has-text("添加")',
                    'button:has-text("Import")',
                    'button:has-text("导入")',
                    '[aria-label*="Add"]',
                ]

                for selector in import_selectors:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        self.page.wait_for_timeout(2000)
                        print(f"已导入源: {source_name}")
                        return True

            print(f"未找到源或导入按钮: {source_name}")
            return False

        except Exception as e:
            print(f"导入源时出错: {e}")
            return False

    def clear_temp_sources(self) -> bool:
        """
        清除所有临时搜索结果

        工作流程：
        1. 检测当前状态（是否有待处理的搜索结果）
        2. 查找"删除"按钮（在"查看"按钮附近）
        3. 点击删除按钮
        4. 确认删除对话框
        5. 验证搜索框恢复可用
        """
        try:
            # 步骤1: 检测状态
            state = self.detect_search_state()
            print(f"当前搜索状态: {state}")

            if state == 'READY':
                print("搜索框已可用，无需清除")
                return True

            if state != 'PENDING_RESULTS':
                print("未检测到待处理的搜索结果")
                return False

            # 步骤2: 查找"删除"按钮（在"查看"按钮附近）
            # 删除按钮通常在查看按钮附近，遍历所有按钮查找
            buttons = self.page.query_selector_all('button')
            delete_btn = None

            for btn in buttons:
                try:
                    if btn.is_visible():
                        text = btn.inner_text().strip()
                        if '删除' in text or 'Delete' in text or 'Remove' in text:
                            delete_btn = btn
                            print(f"找到删除按钮: '{text}'")
                            break
                except:
                    pass

            if not delete_btn:
                print("未找到删除按钮")
                # 备用方法：按 Escape 键
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
                return False

            # 步骤3: 点击删除按钮
            delete_btn.click()
            self.page.wait_for_timeout(1000)

            # 步骤4: 确认删除对话框
            confirm_selectors = [
                'button:has-text("确认")',
                'button:has-text("确定")',
                'button:has-text("Confirm")',
                'button:has-text("OK")',
                'button:has-text("Yes")',
            ]

            for sel in confirm_selectors:
                confirm_btn = self.page.query_selector(sel)
                if confirm_btn and confirm_btn.is_visible():
                    print("点击确认按钮")
                    confirm_btn.click()
                    self.page.wait_for_timeout(2000)
                    break

            # 步骤5: 验证搜索框恢复可用
            self.page.wait_for_timeout(1000)
            final_state = self.detect_search_state()

            if final_state == 'READY':
                print("✅ 临时搜索结果已清除，搜索框恢复可用")
                return True
            else:
                print(f"⚠️ 清除后状态: {final_state}")
                return final_state != 'PENDING_RESULTS'

        except Exception as e:
            print(f"清除临时源时出错: {e}")
            return False

    def smart_chat(self, notebook_name: str, question: str, ensure_chat_mode: bool = True, max_wait: int = 480) -> str:
        """
        智能聊天 - 自动确保在聊天模式，可靠等待回复完成

        Args:
            notebook_name: 笔记本名称
            question: 问题内容
            ensure_chat_mode: 是否自动切换到聊天模式
            max_wait: 最大等待时间（秒），默认480秒(8分钟)

        Returns:
            完整的回复内容
        """
        if not self.open_notebook(notebook_name):
            return ""

        try:
            self.page.wait_for_timeout(3000)

            if ensure_chat_mode:
                # 确保在聊天模式，清除可能的搜索状态
                mode = self.detect_mode()
                if mode == 'source_search':
                    self.clear_temp_sources()
                    self.page.wait_for_timeout(1000)

            # 找到聊天输入框（使用更精确的选择器）
            chat_input = self.page.query_selector('textarea[placeholder*="开始输入"], textarea[aria-label="查询框"]')

            if not chat_input or not chat_input.is_visible():
                # 备用方法
                inputs = self.page.query_selector_all('textarea')
                for inp in inputs:
                    placeholder = inp.get_attribute('placeholder') or ''
                    if '开始输入' in placeholder or inp.get_attribute('aria-label') == '查询框':
                        chat_input = inp
                        break

            if not chat_input:
                print("未找到聊天输入框")
                return ""

            # 输入问题
            chat_input.click()
            self.page.wait_for_timeout(300)
            chat_input.fill(question)
            self.page.wait_for_timeout(500)
            chat_input.press("Enter")

            print(f"问题已发送，等待回复（最多等待 {max_wait} 秒）...")

            # === 阶段1: 等待回复开始生成 ===
            print("等待 AI 开始生成回复...")
            generation_started = False
            for i in range(60):  # 最多等60秒开始生成
                self.page.wait_for_timeout(1000)

                # 检测"停止生成"按钮出现 = 开始生成
                stop_btn_selectors = [
                    'button:has-text("停止生成")',
                    'button:has-text("Stop generating")',
                    'button:has-text("Stop")',
                    '[aria-label*="停止"]',
                    '[aria-label*="Stop"]',
                    'button[aria-label*="stop"]',
                ]

                for sel in stop_btn_selectors:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        generation_started = True
                        print(f"AI 开始生成回复 ({i+1}秒)")
                        break

                if generation_started:
                    break

                # 也检查是否已经有回复内容（快速回复的情况）
                response_el = self.page.query_selector('.response-content, [class*="assistant-message"], [data-message-role="assistant"]')
                if response_el and response_el.is_visible():
                    text = response_el.inner_text().strip()
                    if text and len(text) > 20 and "Getting the context" not in text:
                        generation_started = True
                        print(f"检测到回复内容 ({i+1}秒)")
                        break

                if i % 10 == 0 and i > 0:
                    print(f"等待生成开始... ({i}/60秒)")

            if not generation_started:
                print("⚠️ 未检测到生成开始，继续等待...")

            # === 阶段2: 等待回复生成完成（核心修复） ===
            # 使用文本稳定性检测：连续多次检测文本不变 = 生成完成
            print("等待回复生成完成...")

            last_text = ""
            stable_count = 0
            STABLE_THRESHOLD = 5  # 连续5次(5秒)文本不变认为完成

            for i in range(max_wait):
                self.page.wait_for_timeout(1000)

                # 方法1: 检查"停止生成"按钮是否消失
                stop_btn_visible = False
                stop_btn_selectors = [
                    'button:has-text("停止生成")',
                    'button:has-text("Stop generating")',
                    'button:has-text("Stop")',
                    '[aria-label*="停止生成"]',
                ]

                for sel in stop_btn_selectors:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        stop_btn_visible = True
                        break

                # 方法2: 检查加载指示器
                loading_visible = False
                loading_selectors = [
                    '.loading-indicator',
                    '[class*="loading"]',
                    '[class*="spinner"]',
                    '[class*="generating"]',
                ]

                for sel in loading_selectors:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        loading_visible = True
                        break

                # 方法3: 文本稳定性检测（最可靠）
                current_text = self._get_latest_response_text()

                if current_text and len(current_text) > 50:
                    if current_text == last_text:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_text = current_text

                    # 判断生成完成的条件：
                    # 1. 停止按钮消失 + 无加载指示器 + 文本稳定3次以上
                    # 2. 或者文本稳定达到阈值（即使按钮检测失败）
                    if (not stop_btn_visible and not loading_visible and stable_count >= 3) or stable_count >= STABLE_THRESHOLD:
                        print(f"✅ 回复生成完成 ({i+1}秒, 稳定计数: {stable_count})")
                        break

                # 如果还在生成，显示进度
                if stop_btn_visible or loading_visible:
                    stable_count = 0  # 重置稳定计数
                    if i % 15 == 0 and i > 0:
                        print(f"正在生成... ({i}/{max_wait}秒) | 当前长度: {len(current_text) if current_text else 0} 字符")
                elif i % 30 == 0 and i > 0:
                    print(f"等待中... ({i}/{max_wait}秒) | 稳定计数: {stable_count}/{STABLE_THRESHOLD}")

            # === 阶段3: 额外等待确保完成 ===
            print("额外等待确保内容完整...")
            self.page.wait_for_timeout(3000)

            # 再次检查文本是否还在变化
            final_check_text = self._get_latest_response_text()
            self.page.wait_for_timeout(2000)
            final_check_text2 = self._get_latest_response_text()

            if final_check_text != final_check_text2:
                print("检测到内容仍在更新，继续等待...")
                self.page.wait_for_timeout(5000)

            # === 阶段4: 获取完整回复 ===
            final_response = self._get_latest_response_text()

            if final_response:
                print(f"✅ 获取到回复，长度: {len(final_response)} 字符")
                self._check_response_actions()
                return final_response

            # 备用方法：获取整个聊天区域的文本
            print("尝试备用方法获取回复...")
            chat_area = self.page.query_selector('[class*="chat-container"], [class*="conversation"], main')
            if chat_area:
                full_text = chat_area.inner_text()
                # 尝试提取最后一段回复
                lines = full_text.split('\n')
                response_lines = []
                capture = False
                for line in lines:
                    if "Getting the context" in line:
                        capture = True
                        continue
                    if capture and line.strip():
                        response_lines.append(line.strip())

                if response_lines:
                    result = '\n'.join(response_lines)
                    print(f"✅ 备用方法获取到回复，长度: {len(result)} 字符")
                    return result

            print("❌ 未能获取到回复")
            return ""

        except Exception as e:
            print(f"聊天时出错: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _get_latest_response_text(self) -> str:
        """获取最新的回复文本（内部辅助方法）"""
        try:
            # 尝试多种选择器获取回复
            response_selectors = [
                # NotebookLM 特定选择器
                '[data-message-role="assistant"]',
                '.assistant-message',
                '.response-content',
                # 通用选择器
                '.message-content',
                '[class*="response"]',
                '[class*="answer"]',
                '[class*="chat-message"]',
                '.chat-response',
            ]

            for sel in response_selectors:
                messages = self.page.query_selector_all(sel)
                if messages:
                    # 从最后一条消息开始检查
                    for msg in reversed(messages):
                        try:
                            text = msg.inner_text().strip()
                            # 过滤掉无效响应
                            if text and len(text) > 30 and "Getting the context" not in text:
                                return text
                        except:
                            continue

            return ""
        except Exception as e:
            return ""

    def _check_response_actions(self):
        """检查并显示回复后的可用操作"""
        try:
            actions = []

            # 查找保存为笔记按钮
            save_note_btn = self.page.query_selector('button:has-text("保存为笔记"), button:has-text("Save as note"), [aria-label*="保存"]')
            if save_note_btn and save_note_btn.is_visible():
                actions.append("保存为笔记")

            # 查找复制按钮
            copy_btn = self.page.query_selector('button:has-text("复制"), button:has-text("Copy"), [aria-label*="复制"]')
            if copy_btn and copy_btn.is_visible():
                actions.append("复制")

            # 查找点赞/点踩按钮
            like_btn = self.page.query_selector('[aria-label*="thumb_up"], button:has-text("thumb_up")')
            if like_btn:
                actions.append("点赞/点踩")

            if actions:
                print(f"\n可用操作: {', '.join(actions)}")

        except Exception as e:
            pass  # 静默处理

    def save_response_as_note(self) -> bool:
        """将最近的回复保存为笔记"""
        try:
            # 查找保存为笔记按钮
            save_selectors = [
                'button:has-text("保存为笔记")',
                'button:has-text("Save as note")',
                'button:has-text("Add to note")',
                'button:has-text("添加到笔记")',
                '[aria-label*="保存为笔记"]',
                '[aria-label*="Save as note"]',
            ]

            for sel in save_selectors:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    self.page.wait_for_timeout(2000)
                    print("回复已保存为笔记")
                    return True

            print("未找到保存为笔记按钮")
            return False

        except Exception as e:
            print(f"保存为笔记时出错: {e}")
            return False

    def save_note(self, notebook_name: str, note_content: str, note_title: str = None) -> bool:
        """保存内容到笔记本的笔记区域"""
        if not self.open_notebook(notebook_name):
            return False

        try:
            self.page.wait_for_timeout(3000)

            # 方法1: 点击 Studio 面板中的 "添加笔记" 按钮
            add_note_selectors = [
                'button:has-text("Add note")',
                'button:has-text("添加笔记")',
                '[aria-label*="Add note"]',
                '[aria-label*="添加笔记"]',
                'button:has-text("+")',
            ]

            add_btn = None
            for selector in add_note_selectors:
                btn = self.page.query_selector(selector)
                if btn and btn.is_visible():
                    add_btn = btn
                    break

            if add_btn:
                add_btn.click()
                self.page.wait_for_timeout(1000)

            # 查找笔记输入区域
            note_input_selectors = [
                'textarea[placeholder*="note"]',
                'textarea[placeholder*="笔记"]',
                '[contenteditable="true"]',
                'textarea',
            ]

            note_input = None
            for selector in note_input_selectors:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    if el.is_visible() and el.is_enabled():
                        note_input = el
                        break
                if note_input:
                    break

            if note_input:
                # 如果有标题，先输入标题
                if note_title:
                    note_input.fill(f"# {note_title}\n\n{note_content}")
                else:
                    note_input.fill(note_content)

                self.page.wait_for_timeout(500)

                # 保存笔记
                save_selectors = [
                    'button:has-text("Save")',
                    'button:has-text("保存")',
                    'button[type="submit"]',
                ]

                for selector in save_selectors:
                    save_btn = self.page.query_selector(selector)
                    if save_btn and save_btn.is_visible():
                        save_btn.click()
                        break
                else:
                    # 尝试按 Ctrl+Enter 保存
                    note_input.press("Control+Enter")

                self.page.wait_for_timeout(2000)
                print(f"笔记已保存: {note_title or '无标题'}")
                return True
            else:
                print("未找到笔记输入区域")
                return False

        except Exception as e:
            print(f"保存笔记时出错: {e}")
            return False

    def get_chat_history(self, notebook_name: str, limit: int = 50) -> list:
        """
        获取笔记本的聊天历史记录

        Args:
            notebook_name: 笔记本名称
            limit: 最多返回多少条记录

        Returns:
            聊天记录列表，每条包含 {role: 'user'|'assistant', content: str}
        """
        if not self.open_notebook(notebook_name):
            return []

        try:
            self.page.wait_for_timeout(3000)

            history = []

            # 方法1: 从聊天区域提取消息
            # NotebookLM 的聊天消息通常包含用户问题和AI回答
            chat_selectors = [
                '[class*="chat"]',
                '[class*="message"]',
                '[class*="conversation"]',
            ]

            for selector in chat_selectors:
                elements = self.page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        try:
                            text = el.inner_text().strip()
                            if text and len(text) > 10:
                                # 过滤掉UI元素
                                skip_patterns = [
                                    'thumb_up', 'thumb_down', 'copy_all', 'keep_pin',
                                    '保存到笔记', '正在加载', 'more_vert', 'tunemore_vert',
                                    '搜索结果', '个来源', 'arrow_forward',
                                ]

                                is_ui = False
                                for pattern in skip_patterns:
                                    if pattern in text and len(text) < 50:
                                        is_ui = True
                                        break

                                if not is_ui and text not in [h.get('content', '') for h in history]:
                                    # 简单区分用户和AI消息（AI消息通常更长）
                                    role = 'assistant' if len(text) > 200 else 'user'
                                    history.append({'role': role, 'content': text})
                        except:
                            pass

                    if history:
                        break

            # 方法2: 如果方法1失败，从整个对话区域解析
            if not history:
                try:
                    # 获取中间对话面板的全部文本
                    body_text = self.page.inner_text('body')
                    lines = body_text.split('\n')

                    current_message = []

                    # UI 元素过滤
                    ui_elements = [
                        'thumb_up', 'thumb_down', 'copy_all', 'keep_pin', 'more_vert',
                        '保存到笔记', '正在加载', '搜索结果', 'arrow_forward', 'tunemore_vert',
                        '来源', 'Sources', 'Studio', 'Notes', '笔记', '对话',
                        '添加来源', 'Add source', '创建笔记本', '设置', 'PRO',
                        '收起来源面板', '展开', 'Deep Research', '获取深度报告',
                    ]

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        # 跳过UI元素
                        is_ui = False
                        for ui in ui_elements:
                            if line == ui or (len(line) < 30 and ui in line):
                                is_ui = True
                                break

                        if is_ui:
                            continue

                        # 跳过太短的行（通常是图标）
                        if len(line) < 5:
                            continue

                        # 检测是否是新消息的开始
                        # 用户消息通常较短，以问号结尾
                        if line.endswith('?') or line.endswith('？'):
                            if current_message:
                                content = '\n'.join(current_message)
                                if len(content) > 20:
                                    history.append({'role': 'assistant', 'content': content})
                                current_message = []
                            history.append({'role': 'user', 'content': line})
                        else:
                            current_message.append(line)

                    # 处理最后一条消息
                    if current_message:
                        content = '\n'.join(current_message)
                        if len(content) > 20:
                            history.append({'role': 'assistant', 'content': content})

                except Exception as e:
                    print(f"解析聊天历史时出错: {e}")

            # 去重和限制数量
            seen = set()
            unique_history = []
            for msg in history:
                content_hash = hash(msg['content'][:100])
                if content_hash not in seen:
                    seen.add(content_hash)
                    unique_history.append(msg)

            return unique_history[:limit]

        except Exception as e:
            print(f"获取聊天历史时出错: {e}")
            return []

    def delete_source(self, notebook_name: str, source_name: str) -> bool:
        """删除笔记本中的指定源"""
        if not self.open_notebook(notebook_name):
            return False

        try:
            self.page.wait_for_timeout(3000)

            # 查找源元素
            source_element = None

            # 尝试精确匹配
            source_element = self.page.query_selector(f'text="{source_name}"')

            # 尝试部分匹配
            if not source_element:
                short_name = source_name[:30] if len(source_name) > 30 else source_name
                source_element = self.page.query_selector(f'text=/{short_name}/')

            if not source_element:
                print(f"未找到源: {source_name}")
                return False

            # 尝试通过右键菜单删除
            source_element.click(button="right")
            self.page.wait_for_timeout(1000)

            # 查找删除选项
            delete_selectors = [
                'text="Delete"',
                'text="删除"',
                'text="Remove"',
                'text="移除"',
                '[aria-label*="Delete"]',
                '[aria-label*="Remove"]',
            ]

            for selector in delete_selectors:
                delete_btn = self.page.query_selector(selector)
                if delete_btn and delete_btn.is_visible():
                    delete_btn.click()
                    self.page.wait_for_timeout(1000)

                    # 确认删除
                    confirm = self.page.query_selector(
                        'button:has-text("Delete"), button:has-text("确认"), button:has-text("Remove")'
                    )
                    if confirm:
                        confirm.click()

                    self.page.wait_for_timeout(2000)
                    print(f"源 '{source_name}' 已删除")
                    return True

            # 如果右键菜单不起作用，尝试点击源后找删除按钮
            source_element.click()
            self.page.wait_for_timeout(1000)

            # 查找删除图标或按钮
            delete_icon = self.page.query_selector('[aria-label*="delete"], [aria-label*="Delete"], button:has-text("×")')
            if delete_icon:
                delete_icon.click()
                self.page.wait_for_timeout(2000)
                print(f"源 '{source_name}' 已删除")
                return True

            print(f"无法删除源: {source_name}")
            return False

        except Exception as e:
            print(f"删除源时出错: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="NotebookLM 自动化工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # list 命令
    subparsers.add_parser("list", help="列出所有笔记本")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建新笔记本")
    create_parser.add_argument("--name", required=True, help="笔记本名称")

    # delete 命令
    delete_parser = subparsers.add_parser("delete", help="删除笔记本")
    delete_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # upload 命令
    upload_parser = subparsers.add_parser("upload", help="上传文档")
    upload_parser.add_argument("--file", required=True, help="文件路径")
    upload_parser.add_argument("--notebook", help="目标笔记本名称")

    # audio 命令
    audio_parser = subparsers.add_parser("audio", help="生成播客音频")
    audio_parser.add_argument("--notebook", required=True, help="笔记本名称")
    audio_parser.add_argument("--output", help="输出文件路径")

    # chat 命令
    chat_parser = subparsers.add_parser("chat", help="与笔记本对话")
    chat_parser.add_argument("--notebook", required=True, help="笔记本名称")
    chat_parser.add_argument("--question", required=True, help="问题")

    # sources 命令 - 列出笔记本中的源
    sources_parser = subparsers.add_parser("sources", help="列出笔记本中的源")
    sources_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # delete-source 命令 - 删除指定源
    del_source_parser = subparsers.add_parser("delete-source", help="删除笔记本中的指定源")
    del_source_parser.add_argument("--notebook", required=True, help="笔记本名称")
    del_source_parser.add_argument("--source", required=True, help="源名称")

    # save-note 命令 - 保存笔记
    save_note_parser = subparsers.add_parser("save-note", help="保存内容到笔记本笔记区")
    save_note_parser.add_argument("--notebook", required=True, help="笔记本名称")
    save_note_parser.add_argument("--content", required=True, help="笔记内容")
    save_note_parser.add_argument("--title", help="笔记标题（可选）")

    # login 命令 - 仅用于登录
    subparsers.add_parser("login", help="仅登录 Google 账号")

    # search-sources 命令 - 搜索新源（完整工作流程）
    search_parser = subparsers.add_parser("search-sources", help="搜索新来源（完整工作流程）")
    search_parser.add_argument("--notebook", required=True, help="笔记本名称")
    search_parser.add_argument("--query", required=True, help="搜索查询")
    search_parser.add_argument("--mode", choices=["fast", "deep"], default="fast",
                               help="研究模式: fast(快速研究) 或 deep(深度研究)")
    search_parser.add_argument("--source-type", choices=["web", "drive", "youtube", "link"],
                               default="web", help="来源类型: web/drive/youtube/link")

    # import-result 命令 - 导入搜索结果
    import_result_parser = subparsers.add_parser("import-result", help="导入搜索到的结果")
    import_result_parser.add_argument("--notebook", required=True, help="笔记本名称")
    import_result_parser.add_argument("--title", required=True, help="结果标题（部分匹配）")

    # remove-result 命令 - 移除搜索结果
    remove_result_parser = subparsers.add_parser("remove-result", help="从搜索结果中移除")
    remove_result_parser.add_argument("--notebook", required=True, help="笔记本名称")
    remove_result_parser.add_argument("--title", required=True, help="结果标题（部分匹配）")

    # clear-search 命令 - 清除所有临时搜索结果
    clear_search_parser = subparsers.add_parser("clear-search", help="清除所有临时搜索结果")
    clear_search_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # view-results 命令 - 点击查看按钮
    view_results_parser = subparsers.add_parser("view-results", help="点击查看按钮查看搜索结果")
    view_results_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # inspect-source 命令 - 检查源详情
    inspect_parser = subparsers.add_parser("inspect-source", help="检查源的详细信息")
    inspect_parser.add_argument("--notebook", required=True, help="笔记本名称")
    inspect_parser.add_argument("--source", required=True, help="源名称")

    # smart-chat 命令 - 智能聊天
    smart_chat_parser = subparsers.add_parser("smart-chat", help="智能聊天（自动处理UI模式）")
    smart_chat_parser.add_argument("--notebook", required=True, help="笔记本名称")
    smart_chat_parser.add_argument("--question", required=True, help="问题")
    smart_chat_parser.add_argument("--save-note", action="store_true", help="自动保存回答为笔记")
    smart_chat_parser.add_argument("--max-wait", type=int, default=480, help="最大等待时间（秒），默认480秒(8分钟)")

    # import-source 命令 - 导入临时源（旧命令，保留兼容）
    import_parser = subparsers.add_parser("import-source", help="将临时搜索结果导入为永久源")
    import_parser.add_argument("--notebook", required=True, help="笔记本名称")
    import_parser.add_argument("--source", required=True, help="源名称")

    # detect-mode 命令 - 检测UI模式
    detect_parser = subparsers.add_parser("detect-mode", help="检测当前UI模式(chat/source_search)")
    detect_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # detect-search-state 命令 - 检测搜索状态
    detect_state_parser = subparsers.add_parser("detect-search-state", help="检测搜索状态(READY/PENDING_RESULTS)")
    detect_state_parser.add_argument("--notebook", required=True, help="笔记本名称")

    # chat-history 命令 - 查看聊天历史
    history_parser = subparsers.add_parser("chat-history", help="查看笔记本的聊天历史记录")
    history_parser.add_argument("--notebook", required=True, help="笔记本名称")
    history_parser.add_argument("--limit", type=int, default=20, help="最多显示多少条记录 (默认20)")
    history_parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式 (默认text)")

    # 通用参数
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument("--user-profile", action="store_true",
                        help="使用你的默认 Chrome Profile（需关闭其他 Chrome 窗口）")
    parser.add_argument("--browser", choices=["chrome", "safari", "webkit", "firefox"],
                        default="chrome", help="选择浏览器引擎 (默认 chrome 隔离 Profile，不影响你的浏览器)")
    parser.add_argument("--instance", type=str, default=None,
                        help="手动指定实例名称（如 nb_01）。默认自动根据笔记本名称分配实例")
    parser.add_argument("--no-auto-instance", action="store_true",
                        help="禁用自动实例分配，使用共享 Profile（可能导致多窗口冲突）")
    parser.add_argument("--cdp-url", type=str, default=None,
                        help="通过 CDP 连接已运行的 Chrome (如 http://127.0.0.1:9222)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="自定义超时时间（秒）。覆盖默认值：chat=480, fast=1200, deep=1800")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 获取目标笔记本名称（用于自动实例分配）
    target_notebook = getattr(args, 'notebook', None)

    # 自动实例分配：默认开启，除非指定 --no-auto-instance
    auto_instance = not getattr(args, 'no_auto_instance', False)

    nlm = NotebookLMAutomation(
        headless=args.headless,
        use_user_profile=getattr(args, 'user_profile', False),
        browser_type=args.browser,
        instance=args.instance,
        auto_instance=auto_instance,
        target_notebook=target_notebook,
        cdp_url=getattr(args, 'cdp_url', None)
    )

    try:
        nlm.start()

        if args.command == "login":
            if nlm.ensure_logged_in():
                print("\n登录完成！现在可以使用其他命令了。")
            else:
                print("\n登录失败，请重试。")

        elif args.command == "list":
            notebooks = nlm.list_notebooks()
            if notebooks:
                print("\n笔记本列表:")
                for i, name in enumerate(notebooks, 1):
                    print(f"  {i}. {name}")
            else:
                print("没有找到笔记本，或者需要先登录")

        elif args.command == "create":
            nlm.create_notebook(args.name)

        elif args.command == "delete":
            nlm.delete_notebook(args.notebook)

        elif args.command == "upload":
            nlm.upload_document(args.file, args.notebook)

        elif args.command == "audio":
            nlm.generate_audio(args.notebook, args.output)

        elif args.command == "chat":
            # chat 统一使用 smart_chat 实现，更可靠
            answer = nlm.smart_chat(args.notebook, args.question)
            if answer:
                print(f"\n回答:\n{answer}")
            else:
                print("未获取到回复")

        elif args.command == "sources":
            sources = nlm.list_sources(args.notebook)
            if sources:
                print(f"\n笔记本 '{args.notebook}' 的源列表:")
                for i, name in enumerate(sources, 1):
                    print(f"  {i}. {name}")
            else:
                print("没有找到源，或源面板结构未识别")

        elif args.command == "delete-source":
            nlm.delete_source(args.notebook, args.source)

        elif args.command == "save-note":
            nlm.save_note(args.notebook, args.content, args.title)

        elif args.command == "search-sources":
            source_type = getattr(args, 'source_type', 'web')
            results = nlm.search_sources(args.notebook, args.query, args.mode, source_type, timeout=getattr(args, 'timeout', None))
            if results:
                print(f"\n搜索结果 (来源类型: {source_type}, 模式: {args.mode}):")
                for i, name in enumerate(results, 1):
                    print(f"  {i}. {name}")
            else:
                print("没有找到相关源")

        elif args.command == "import-result":
            if nlm.open_notebook(args.notebook):
                if nlm.import_search_result(args.title):
                    print(f"已成功导入: {args.title}")
                else:
                    print(f"导入失败: {args.title}")

        elif args.command == "remove-result":
            if nlm.open_notebook(args.notebook):
                if nlm.remove_search_result(args.title):
                    print(f"已成功移除: {args.title}")
                else:
                    print(f"移除失败: {args.title}")

        elif args.command == "clear-search":
            if nlm.open_notebook(args.notebook):
                if nlm.clear_temp_sources():
                    print("已清除所有临时搜索结果")
                else:
                    print("清除失败")

        elif args.command == "view-results":
            if nlm.open_notebook(args.notebook):
                if nlm.click_view_results():
                    # 获取并显示结果
                    results = nlm.get_search_results_with_actions()
                    if results:
                        print("\n搜索结果列表:")
                        for i, r in enumerate(results, 1):
                            status = []
                            if r.get('can_import'):
                                status.append("可导入")
                            if r.get('can_remove'):
                                status.append("可移除")
                            status_str = f" [{', '.join(status)}]" if status else ""
                            print(f"  {i}. {r['title'][:60]}{status_str}")
                else:
                    print("未找到查看按钮")

        elif args.command == "inspect-source":
            if nlm.open_notebook(args.notebook):
                info = nlm.inspect_source(args.source)
                if info:
                    print(f"\n源详情:")
                    print(f"  标题: {info.get('title', 'N/A')}")
                    print(f"  类型: {info.get('type', 'N/A')}")
                    print(f"  URL: {info.get('url', 'N/A')}")
                    if info.get('preview'):
                        print(f"  预览: {info['preview'][:200]}...")
                else:
                    print("无法获取源信息")

        elif args.command == "smart-chat":
            answer = nlm.smart_chat(args.notebook, args.question, max_wait=getattr(args, "max_wait", 480))
            if answer:
                print(f"\n回答:\n{answer}")
                # 如果指定了保存笔记
                if getattr(args, 'save_note', False):
                    nlm.save_note(args.notebook, answer, f"问答: {args.question[:30]}...")
                    print("\n✅ 回答已保存为笔记")
                else:
                    print("\n提示: 添加 --save-note 参数可自动保存回答为笔记")
            else:
                print("未获取到回复")

        elif args.command == "import-source":
            if nlm.open_notebook(args.notebook):
                if nlm.import_temp_source(args.source):
                    print(f"源 '{args.source}' 已成功导入")
                else:
                    print(f"导入源失败: {args.source}")

        elif args.command == "detect-mode":
            if nlm.open_notebook(args.notebook):
                mode = nlm.detect_mode()
                print(f"\n当前UI模式: {mode}")
                if mode == 'chat':
                    print("  说明: 聊天模式 - 可以与现有源对话")
                elif mode == 'source_search':
                    print("  说明: 源搜索模式 - 可以搜索添加新源")
                else:
                    print("  说明: 未识别的模式")

        elif args.command == "detect-search-state":
            if nlm.open_notebook(args.notebook):
                nlm.page.wait_for_timeout(3000)
                state = nlm.detect_search_state()
                print(f"\n搜索状态: {state}")
                if state == 'READY':
                    print("  说明: 搜索框可用，可以进行新搜索")
                elif state == 'PENDING_RESULTS':
                    print("  说明: 有待处理的搜索结果")
                    print("  操作: 使用 clear-search 命令清除，或 view-results 查看并导入/移除")
                else:
                    print("  说明: 未知状态，可能需要刷新页面")

        elif args.command == "chat-history":
            history = nlm.get_chat_history(args.notebook, args.limit)
            if history:
                output_format = getattr(args, 'format', 'text')
                if output_format == 'json':
                    import json
                    print(json.dumps(history, ensure_ascii=False, indent=2))
                else:
                    print(f"\n聊天历史记录 ({len(history)} 条):")
                    print("=" * 60)
                    for i, msg in enumerate(history, 1):
                        role_display = "👤 用户" if msg['role'] == 'user' else "🤖 助手"
                        content = msg['content']
                        # 截断过长的内容
                        if len(content) > 500:
                            content = content[:500] + "..."
                        print(f"\n[{i}] {role_display}:")
                        print(f"{content}")
                        print("-" * 40)
            else:
                print("没有找到聊天记录")

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        nlm.close()


if __name__ == "__main__":
    main()
