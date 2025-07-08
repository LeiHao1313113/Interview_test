import json
import scrapy
from scrapy.exporters import JsonItemExporter
from urllib.parse import urljoin
from itemadapter import ItemAdapter


# 定义规范的数据结构
class NikeShoeItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    color = scrapy.Field()
    description = scrapy.Field()
    image_url = scrapy.Field()
    size = scrapy.Field()
    sku = scrapy.Field()


class NikeShoeSpider(scrapy.Spider):
    name = "nike_shoe"
    allowed_domains = ["www.nike.com.cn"]
    start_urls = ["https://www.nike.com.cn/w/"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化JSON导出器
        self.json_file = open('nike_shoes.json', 'wb')
        self.exporter = JsonItemExporter(
            self.json_file,
            encoding='utf-8',
            ensure_ascii=False,
            indent=4
        )
        self.exporter.start_exporting()

    def close(self, reason):
        # 爬虫关闭时完成导出
        self.exporter.finish_exporting()
        self.json_file.close()

    def _extract_json_data(self, response, script_id="__NEXT_DATA__"):
        """从响应中提取指定script标签的JSON数据"""
        try:
            script_data = response.xpath(f'//script[@id="{script_id}"]/text()').get()
            return json.loads(script_data) if script_data else None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}, URL: {response.url}")
            return None

    def parse(self, response):
        data = self._extract_json_data(response)
        if not data:
            return

        try:
            products = data["props"]["pageProps"]["initialState"]["Wall"]["products"]
            for product in products:
                detail_url = urljoin("https://www.nike.com.cn/", product["url"][14:])
                yield response.follow(
                    detail_url,
                    callback=self.parse_detail,
                    meta={"product_base": {
                        "title": product["title"],
                        "color": product["colorDescription"]
                    }}
                )
        except KeyError as e:
            self.logger.error(f"商品列表字段缺失: {e}")

    def parse_detail(self, response):
        detail_data = self._extract_json_data(response)
        if not detail_data:
            return

        try:
            product = detail_data["props"]["pageProps"]["selectedProduct"]
            base_info = response.meta["product_base"]

            item = NikeShoeItem(
                title=base_info["title"],
                price=product["prices"]["currentPrice"],
                color=base_info["color"],
                description=product["productInfo"]["productDescription"],
                image_url=product["contentImages"][0]["properties"]["squarish"]["url"]
            )

            for size in product["sizes"]:
                size_item = NikeShoeItem(item)
                size_item.update({
                    "size": size["localizedLabel"],
                    "sku": size["merchSkuId"]
                })
                self.exporter.export_item(ItemAdapter(size_item).asdict())
                yield size_item

        except (KeyError, IndexError) as e:
            self.logger.error(f"商品详情解析失败: {e}, URL: {response.url}")