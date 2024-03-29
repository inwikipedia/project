# -*- coding: utf-8 -*-
# @Time    : 2019/7/3 13:38
# @Author  : project
# @File    : spider.py
# @Software: PyCharm
import re
import csv
import json
import requests
import threading
import pandas as pd
from datetime import datetime
from retrying import retry
from fake_useragent import UserAgent
"""
汽车之家全系车型价格
"""


def run_time(func):
    def new_func(*args, **kwargs):
        start_time = datetime.now()
        print("程序开始时间：{}".format(start_time))
        func(*args, **kwargs)
        end_time = datetime.now()
        print("程序结束时间：{}".format(end_time))
        print("程序执行用时：{}s".format((end_time - start_time)))

    return new_func


class Spider:
    def __init__(self):
        # 获取随机请求头
        self.headers = {"User-Agent": UserAgent().random}
        self.lock = threading.Lock()
        self.count = 0

    @retry(stop_max_attempt_number=1)
    def _parse_url(self, url):
        """url请求"""
        while True:
            try:
                response = requests.get(url, headers=self.headers, timeout=1)
            except Exception as e:
                print(e)
                continue
            return response

    def get_model(self):
        """获取所有车型数据"""
        # 所有车型js文件
        url = 'https://car.autohome.com.cn/javascript/NewSpecCompare.js?20131010'
        response = self._parse_url(url)
        # GBK解码
        content = response.content.decode('GBK')
        # 剔除开头和结尾处多余字符 转换为json
        content = content.replace('var listCompare$100= ', '').replace(';', '')
        content = json.loads(content)
        for i in content:
            # 品牌首字母,名称,车系列表
            che_id, brand_l, brand_n, brand_list,  = i['I'], i['L'], i['N'], i['List']
            for q in brand_list:
                # 车系名称,车型列表
                car_l, car_list = q['N'], q['List']
                for t in car_list:
                    # 车型ID, 车型名称
                    model_l = t['I']
                    model_n = t['N']
                    yield che_id, brand_l, brand_n, car_l, model_n, model_l

    def model_csv(self):
        """保存所有车型数据"""
        data = []
        for i in self.get_model():
            che_id, brand_l, brand_n, car_l, model_n, model_l = i
            data.append([brand_l, brand_n, car_l, model_n, datetime.now()])
        name = ['品牌索引', '品牌名称', '车系名称', '车型', '时间']
        df = pd.DataFrame(columns=name, data=data)
        df.to_csv('model.csv', mode='a', encoding='utf-8')
        print('车型数据保存成功')

    def get_dealer(self):
        """获取经销商信息"""

        for i in self.get_model():
            che_id, brand_l, brand_n, car_l, model_n, model_l = i
            # 根据车型ID和区域编码获取经销商信息
            url = 'https://www.autohome.com.cn/ashx/dealer/AjaxDealersBySeriesId.ashx?seriesId={}&cityId=110100'.format(str(model_l))
            response = self._parse_url(url)
            # 无数据跳过
            if not response.json()['result']['list']:
                # self.scv_data([[brand_l, brand_n, car_l, model_n]])
                print('暂无经销商信息')
                continue
            # 获取经销商信息 主要取经销商ID 用来获取价格
            contents = response.json()['result']['list']
            print('[{}{}]数据请求中'.format(car_l, model_n))
            for con in contents:
                data = []
                # dealer['dealerId'] = con['dealerId']  # 经销商ID
                dealerName = con['dealerInfoBaseOut']['dealerName']  # 经销商名称
                countyName = con['dealerInfoBaseOut']['countyName']  # 所在地区
                companySimple = con['dealerInfoBaseOut']['companySimple']  # 简称
                dealerAdd = con['dealerInfoBaseOut']['address']  # 地址
                orderRange = con['dealerInfoBaseOut']['orderRangeTitle']  # 销售区域
                phone = con['yphone']  # 电话
                showPhone = con['dealerInfoBaseOut']['showPhone']  # 400电话
                # print(str(con['dealerId']), str(model_l))
                for u in self.get_price(str(con['dealerId']), str(model_l)):
                    SpecName, OriginalPrice, Price = u
                    year = re.findall(r'(.*?)款', SpecName)[0]
                    specname = re.findall(r'款(.*?)$', SpecName)[0]
                    data.append([brand_l, brand_n, car_l, model_n, SpecName, OriginalPrice, Price, dealerName,
                                 countyName, companySimple, dealerAdd, orderRange, phone, showPhone, datetime.now()])
                    # data.append([che_id, brand_n, model_l, model_n, con['dealerId'], year, specname])
                    # print('[{} {}]'.format(model_n, SpecName))
                    print(data)
                self.scv_data(data)
                # self.a_b(data)

    def get_price(self, dealerId, seriesId):
        """获取价格"""
        url = 'https://dealer.autohome.com.cn/Ajax/GetSpecListByDealer?dealerId={}&seriesId={}'.format(dealerId, seriesId)
        # print(url)
        # 根据经销商ID 和 车型ID 获取车型价格
        response = self._parse_url(url)
        # 无数据跳过
        if not response.json()['result']['list']:
            print('暂无经销商信息')
            return
        # 获取经销商信息 主要取经销商ID 用来获取价格
        contents = response.json()['result']['list']
        for con in contents:
            # 汽车型号
            SpecName = con['SpecName']
            # 指导价
            OriginalPrice = con['OriginalPrice']
            # 参考价
            Price = con['Price']
            yield SpecName, OriginalPrice, Price

    def scv_data(self, data):
        """
        '品牌索引', '品牌名称', '车系名称', '车型', '汽车型号', '指导价', '参考价', '经销商名称',
        '地区', '简称', '地址', '销售区域', '电话1', '电话2', '时间'
        :param data:
        :return:
        """
        self.count += 1
        with open("demo.csv", "a+", encoding='utf-8', newline="") as f:
            k = csv.writer(f, delimiter=',')
            with open("demo.csv", "r", encoding='utf-8', newline="") as f1:
                reader = csv.reader(f1)
                if not [row for row in reader]:
                    k.writerow(['品牌索引', '品牌名称', '车系名称', '车型', '汽车型号', '指导价', '参考价', '经销商名称',
                                '地区', '简称', '地址', '销售区域', '电话1', '电话2', '时间'])
                    k.writerows(data)
                    print('第[{}]条数据插入成功'.format(self.count))
                else:
                    k.writerows(data)
                    print('第[{}]条数据插入成功'.format(self.count))

    def a_b(self, data):
        """
        保存 '品牌ID', '品牌名称', '车系ID', '车系名称', '车型ID', '年份', '车型名称'
        :param data:
        :return:
        """

        self.count += 1
        with open("全系车型数据.csv", "a+", encoding='utf-8', newline="") as f:
            k = csv.writer(f, delimiter=',')
            with open("全系车型数据.csv", "r", encoding='utf-8', newline="") as f1:
                reader = csv.reader(f1)
                if not [row for row in reader]:
                    k.writerow(['品牌ID', '品牌名称', '车系ID', '车系名称', '车型ID', '年份', '车型名称'])
                    k.writerows(data)
                    print('第[{}]条数据插入成功'.format(self.count))
                else:
                    k.writerows(data)
                    print('第[{}]条数据插入成功'.format(self.count))

    @run_time
    def run(self):
        # 获取车型数据
        # self.model_csv()
        # 获取所有信息
        self.get_dealer()


if __name__ == '__main__':
    spider = Spider()
    spider.run()
