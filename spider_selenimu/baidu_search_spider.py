# -*- coding: utf-8 -*-
import os
import threading
import time

import requests
from selenium import webdriver
from libs.common import *
from selenium.webdriver import DesiredCapabilities, ActionChains

"""
百度图片搜索（只保存图片链接到文件）
"""

# 遇到错误后休息时长
EXCEPTION_SLEEP_INTERVAL = 10

# 是否自动换IP（启动浏览器时更换IP）
IS_AUTO_CHANGE_IP = False

BASE_URL = 'https://image.baidu.com/search/index?tn=baiduimage&ipn=r&ct=201326592&cl=2&lm=-1&st=-1&fm=result&fr=&sf=1&fmq=1535352159261_R&pv=' \
           '&ic=0&nc=1&z=&se=1&showtab=0&fb=0&width=&height=&face=0&istype=2&ie=utf-8&word=%s'

PHANTOMJS_SLEEP_TIME = 3

KEYWORDS = []
with open('keywords.txt', mode='r', encoding='utf-8') as f:
    lines = f.readlines()
    for line in lines:
        keyword = line.strip('\n')
        KEYWORDS.append(keyword)

URL_SAVE_DIR = 'baidu_url'
DOWNLOAD_DIR = 'baidu_download'
NEED_DOWNLOAD_URL_DIR = 'download_url'


class DownloadConsumer(threading.Thread):
    """
    更新歌手线程，用于往数据库中更新数据
    """

    def __init__(self, thread_name, urls):
        threading.Thread.__init__(self)
        self.__module = self.__class__.__name__
        self.thread_name = thread_name
        self.urls = urls

    @staticmethod
    def write_file_log(msg, __module='', level='error'):
        filename = os.path.split(__file__)[1]
        if level == 'debug':
            logging.getLogger().debug('File:' + filename + ', ' + __module + ': ' + msg)
        elif level == 'warning':
            logging.getLogger().warning('File:' + filename + ', ' + __module + ': ' + msg)
        else:
            logging.getLogger().error('File:' + filename + ', ' + __module + ': ' + msg)

    # debug log
    def debug(self, msg, func_name=''):
        __module = "%s.%s" % (self.__module, func_name)
        msg = "thread_name: %s, %s" % (self.thread_name, msg)
        self.write_file_log(msg, __module, 'debug')

    # error log
    def error(self, msg, func_name=''):
        __module = "%s.%s" % (self.__module, func_name)
        msg = "thread_name: %s, %s" % (self.thread_name, msg)
        self.write_file_log(msg, __module, 'error')

    def download_images(self, imgs, save_dir):
        sess = requests.Session()
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        requests_proxies = {
            'http': 'http:127.0.0.1:1080',
            'https': 'https:127.0.0.1:1080',
        }
        i = 0
        for img in imgs:
            i += 1
            self.debug('%s - 第 %s / %s 个' % (self.thread_name, str(i), str(len(imgs))))
            img = img.split('"')[-1].replace('\\', '')
            try:
                response = sess.get(img, proxies=requests_proxies)
                if response.status_code == '200':
                    img_content = response.content
                    img_name = DOWNLOAD_DIR + os.path.sep + get_standard_file_name(img)
                    with open(img_name, 'wb') as f:
                        f.write(img_content)
                    self.debug('pic saved completed')
                else:
                    self.debug('pic download fail: %s - %s' % (str(response.status_code), str(img)))
            except Exception as e:
                self.error('pic download fail: %s - %s' % (str(response.status_code), str(img)))

        self.debug('%s - all pics saved' % self.thread_name)

    def main(self):
        try:
            # 下载指定文件中的URL资源
            dirs = os.listdir(NEED_DOWNLOAD_URL_DIR)
            thread_list = list()
            for file in dirs:
                urls = list()
                with open(file=file, mode='r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines:
                        urls.append(line.strip())
                thread = DownloadConsumer('thread - %s' % str(file), urls)
                thread_list.append(thread)
            # 开启线程
            for t in thread_list:
                t.start()
            for t in thread_list:
                t.join()
        except Exception as e:
            self.error(str(e), get_current_func_name())


class BaiduSoiderSelenium:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    init_log(console_level=logging.DEBUG, file_level=logging.DEBUG, logfile="logs/" + str(os.path.split(__file__)[1].split(".")[0]) + ".log")
    init_log(console_level=logging.ERROR, file_level=logging.ERROR, logfile="logs/" + str(os.path.split(__file__)[1].split(".")[0]) + "_error.log")

    if not os.path.exists(URL_SAVE_DIR):
        os.makedirs(URL_SAVE_DIR)

    HOST = 'https://image.baidu.com'
    save_file_name = 'default'

    def __init__(self):
        self.__module = self.__class__.__name__
        self.browser = None

    def get_browser_chrome(self):
        if self.browser:
            self.browser.close()
            self.browser.quit()
        chrome_options = webdriver.ChromeOptions()
        # 无头浏览
        # chrome_options.headless = True
        # 禁止加载图片
        prefs = {"profile.managed_default_content_settings.images": 2}
        if IS_AUTO_CHANGE_IP:
            proxy_ip = get_available_ip_proxy()
            if proxy_ip:
                self.debug('使用代理IP：%s' % proxy_ip)
                chrome_options.add_argument('--proxy-server={0}'.format(proxy_ip))
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument('user-agent="%s"' % get_user_agent())
        self.browser = webdriver.Chrome(chrome_options=chrome_options)

    def close_browser(self):
        if self.browser:
            try:
                self.browser.close()
                self.browser.quit()
            except Exception as e:
                pass

    def get_browser_phantomjs(self):
        if self.browser:
            try:
                self.browser.close()
                self.browser.quit()
            except Exception as e:
                pass
        service_args = None
        if IS_AUTO_CHANGE_IP:
            proxy_ip = get_available_ip_proxy()
            if proxy_ip:
                self.debug('使用代理IP：%s' % proxy_ip)
                service_args = [
                    '--proxy=%s' % proxy_ip,  # 代理 IP：prot
                    '--proxy-type=http',  # 代理类型：http/https
                    '--load-images=no',  # 关闭图片加载（可选）
                    '--disk-cache=yes',  # 开启缓存（可选）
                    '--ignore-ssl-errors=true'  # 忽略https错误（可选）
                ]
        if not service_args:
            service_args = [
                '--load-images=no',  # 关闭图片加载（可选）
                '--disk-cache=yes',  # 开启缓存（可选）
                '--ignore-ssl-errors=true'  # 忽略https错误（可选）
            ]
        dcap = dict(DesiredCapabilities.PHANTOMJS)
        dcap["phantomjs.page.settings.userAgent"] = get_user_agent()
        self.browser = webdriver.PhantomJS(service_args=service_args, desired_capabilities=dcap)
        # 设置超时选项（get网页超时）
        self.browser.set_page_load_timeout(15)

    def init_browser(self, force_init=False):
        try:
            if not self.browser or force_init:
                self.debug('>>> 初始化 browser ...')
                self.get_browser_chrome()
        except Exception as e:
            self.error(str(e), get_current_func_name())

    def start_requests(self):
        """
        开始获取请求
        """
        self.init_browser()
        for keyword in KEYWORDS:
            try:
                url = BASE_URL % keyword
                self.browser.get(url=url)

                # 向下拉更新
                for __ in range(30):
                    # multiple scrolls needed to show all 400 images
                    self.browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)

                items = list()
                detail_urls = self.browser.find_elements_by_xpath('//div[@class="imgpage"]/ul/li/div/a')
                for item in detail_urls:
                    url = item.get_attribute('href')
                    if self.HOST not in url:
                        url = self.HOST + url
                    items.append(url)

                for url in items:
                    # 处理图片详情
                    self.handle_item(url, keyword)
            except Exception as e:
                self.error(str(e), get_current_func_name())
                time.sleep(EXCEPTION_SLEEP_INTERVAL)
                self.init_browser(force_init=True)
        self.close_browser()

    @staticmethod
    def get_clean_name(original_title):
        return original_title.replace('⋅', '')

    def handle_item(self, url, keyword):
        """
        处理原始图片
        """
        try:
            self.browser.get(url)
            # time.sleep(1)
            imgage_ori_url = self.browser.find_elements_by_xpath('//img[@id="hdFirstImgObj"]')
            if not os.path.exists(URL_SAVE_DIR):
                os.makedirs(URL_SAVE_DIR)
            if imgage_ori_url and len(imgage_ori_url) > 0:
                imgage_ori_url = imgage_ori_url[0].get_attribute('src')
                with open(URL_SAVE_DIR + os.path.sep + get_standard_file_name(keyword) + '.txt', mode='a+', encoding='utf-8') as f:
                    f.write(imgage_ori_url)
                    f.write('\n')
        except Exception as e:
            self.error(str(e))
            time.sleep(EXCEPTION_SLEEP_INTERVAL)
            self.init_browser(force_init=True)

    @staticmethod
    def write_file_log(msg, __module='', level='error'):
        filename = os.path.split(__file__)[1]
        if level == 'debug':
            logging.getLogger().debug('File:' + filename + ', ' + __module + ': ' + msg)
        elif level == 'warning':
            logging.getLogger().warning('File:' + filename + ', ' + __module + ': ' + msg)
        else:
            logging.getLogger().error('File:' + filename + ', ' + __module + ': ' + msg)

    # debug log
    def debug(self, msg, func_name=''):
        __module = "%s.%s" % (self.__module, func_name)
        self.write_file_log(msg, __module, 'debug')

    # error log
    def error(self, msg, func_name=''):
        __module = "%s.%s" % (self.__module, func_name)
        self.write_file_log(msg, __module, 'error')


if __name__ == '__main__':
    spider = BaiduSoiderSelenium()
    spider.start_requests()
