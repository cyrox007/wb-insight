from fastapi import APIRouter, Request

from core.logger import setup_logger
from utils.responce_helps import response_success

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = setup_logger(__name__)

@router.get("/")
async def dashboard(request: Request):
    products = [
        { 'id': 1, 'name': 'Электросталь', 'sales': 2722, 'profit': 1500 },
        { 'id': 2, 'name': 'Коледино', 'sales': 1323, 'profit': 800 },
        { 'id': 3, 'name': 'Казань', 'sales': 638, 'profit': 400 },
        { 'id': 4, 'name': 'Рязань', 'sales': 746, 'profit': 500 },
        { 'id': 5, 'name': 'Невинномысск', 'sales': 550, 'profit': 300 },
        { 'id': 6, 'name': 'Екатеринбург', 'sales': 473, 'profit': 250 },
        { 'id': 7, 'name': 'Самара', 'sales': 460, 'profit': 200 },
        { 'id': 8, 'name': 'Санкт-Петербург', 'sales': 388, 'profit': 180 },
        { 'id': 9, 'name': 'Новосибирск', 'sales': 259, 'profit': 150 },
        { 'id': 10, 'name': 'Котовск', 'sales': 157, 'profit': 100 },
        { 'id': 11, 'name': 'Владимир', 'sales': 124, 'profit': 80 },
        { 'id': 12, 'name': 'Волгоград', 'sales': 122, 'profit': 70 },
        { 'id': 13, 'name': 'Воронеж', 'sales': 105, 'profit': 60 },
        { 'id': 14, 'name': 'Саратов', 'sales': 74, 'profit': 40 },
        { 'id': 15, 'name': 'Екатеринбург', 'sales': 52, 'profit': 30 },
        { 'id': 16, 'name': 'Астана', 'sales': 15, 'profit': 10 },
        { 'id': 17, 'name': 'Белая дача', 'sales': 15, 'profit': 10 },
        { 'id': 18, 'name': 'Актобе', 'sales': 13, 'profit': 8 },
        { 'id': 19, 'name': 'Атакент', 'sales': 8, 'profit': 5 },
        { 'id': 20, 'name': 'Калининград', 'sales': 7, 'profit': 4 },
        { 'id': 21, 'name': 'СЦ Ереван', 'sales': 5, 'profit': 3 },
        { 'id': 22, 'name': 'Чашниково', 'sales': 3, 'profit': 2 },
        { 'id': 23, 'name': 'Обухово', 'sales': 1, 'profit': 1 },
        { 'id': 24, 'name': 'СЦ Барнаул', 'sales': 1, 'profit': 1 }
    ]

    sizeChart = [
        { 'size': '40', 'quantity': 2447, 'inTransit': 87 },
        { 'size': '42', 'quantity': 1939, 'inTransit': 261 },
        { 'size': '44', 'quantity': 1534, 'inTransit': 301 },
        { 'size': '46', 'quantity': 1380, 'inTransit': 203 },
        { 'size': '48', 'quantity': 1381, 'inTransit': 238 },
        { 'size': '50', 'quantity': 973, 'inTransit': 213 },
        { 'size': '52', 'quantity': 752, 'inTransit': 207 },
        { 'size': '54', 'quantity': 587, 'inTransit': 111 },
        { 'size': '56', 'quantity': 428, 'inTransit': 83 },
        { 'size': '58', 'quantity': 7, 'inTransit': 0 }
    ]

    selectedProducts = [
        {
            'id': 1,
            'name': 'Темно-синее пальто',
            'price': '12 999',
            'image': 'https://placehold.co/200x300/2c3e50/ffffff?text=Пальто',
            'sales': 150,
            'rating': 4.8
        },
        {
            'id': 2,
            'name': 'Черная зимняя куртка',
            'price': '15 999',
            'image': 'https://placehold.co/200x300/000000/ffffff?text=Куртка',
            'sales': 120,
            'rating': 4.5
        },
        {
            'id': 3,
            'name': 'Бежевое пуховое пальто',
            'price': '18 999',
            'image': 'https://placehold.co/200x300/d2b48c/ffffff?text=Пуховик',
            'sales': 95,
            'rating': 4.9
        },
        {
            'id': 4,
            'name': 'Зеленое зимнее пальто',
            'price': '14 999',
            'image': 'https://placehold.co/200x300/556b2f/ffffff?text=Пальто',
            'sales': 85,
            'rating': 4.3
        }
    ]

    abcAnalysis = [
        { 'id': 1, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '182440753', 'revenue': '624 572,9', 'profit': '348 148,4', 'share': '22,8%', 'cumulativePercent': '22,8%', 'category': 'A' },
	    { 'id': 2, 'sellerSku': 'РубашкаШелк-01-зп', 'wbSku': '152048084', 'revenue': '324 707,9', 'profit': '172 073,6', 'share': '11,3%', 'cumulativePercent': '34,1%', 'category': 'A' },
	    { 'id': 3, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '219169078', 'revenue': '208 559,2', 'profit': '143 802,8', 'share': '9,4%', 'cumulativePercent': '43,6%', 'category': 'A' },
	    { 'id': 4, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '190442797', 'revenue': '189 835,0', 'profit': '111 008,8', 'share': '7,3%', 'cumulativePercent': '50,9%', 'category': 'A' },
	    { 'id': 5, 'sellerSku': 'ВолнистаяБлузка-0', 'wbSku': '388639444', 'revenue': '177 276,6', 'profit': '99 807,4', 'share': '6,5%', 'cumulativePercent': '57,4%', 'category': 'A' },
	    { 'id': 6, 'sellerSku': 'ПлатьеОдноПлехо-1', 'wbSku': '391354791', 'revenue': '214 603,6', 'profit': '91 153,8', 'share': '6,0%', 'cumulativePercent': '63,4%', 'category': 'A' },
	    { 'id': 7, 'sellerSku': 'АтласРубашкаНова', 'wbSku': '334837164', 'revenue': '120 756,0', 'profit': '84 180,7', 'share': '5,5%', 'cumulativePercent': '68,9%', 'category': 'A' },
	    { 'id': 8, 'sellerSku': 'РубашкаШелк-01-ч', 'wbSku': '144826387', 'revenue': '138 890,4', 'profit': '80 063,8', 'share': '5,3%', 'cumulativePercent': '74,2%', 'category': 'A' },
	    { 'id': 9, 'sellerSku': 'БлузкаПланка-01-б', 'wbSku': '104098349', 'revenue': '100 457,5', 'profit': '66 591,8', 'share': '4,4%', 'cumulativePercent': '78,5%', 'category': 'B' },
	    { 'id': 10, 'sellerSku': 'ПальтоХалатДрап-С', 'wbSku': '170206280', 'revenue': '114 379,2', 'profit': '58 267,9', 'share': '3,8%', 'cumulativePercent': '82,3%', 'category': 'B' }
    ]

    chartData = [
        { 'label': '01.10', 'value': 80 },
        { 'label': '02.10', 'value': 90 },
        { 'label': '03.10', 'value': 70 },
        { 'label': '04.10', 'value': 75 },
        { 'label': '05.10', 'value': 65 },
        { 'label': '06.10', 'value': 70 },
        { 'label': '07.10', 'value': 75 },
        { 'label': '08.10', 'value': 85 },
        { 'label': '09.10', 'value': 80 },
        { 'label': '10.10', 'value': 60 },
        { 'label': '11.10', 'value': 70 },
        { 'label': '12.10', 'value': 90 },
        { 'label': '13.10', 'value': 65 },
        { 'label': '14.10', 'value': 70 },
        { 'label': '15.10', 'value': 95 },
        { 'label': '16.10', 'value': 80 },
        { 'label': '17.10', 'value': 60 },
        { 'label': '18.10', 'value': 75 },
        { 'label': '19.10', 'value': 80 }
    ]
    return response_success(
        products=products,
        sizeChart=sizeChart,
        selectedProducts=selectedProducts,
        abcAnalysis=abcAnalysis,
        chartData=chartData
    )