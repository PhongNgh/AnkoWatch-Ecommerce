from flask import render_template, request
from app import mongo
from datetime import datetime, timedelta
from calendar import month_name
import pytz

def get_dashboard_stats():
    # Get the filter type and selected year from the request
    filter_type = request.args.get('filter', 'month')  # Options: 'week', 'month', 'quarter', 'year'
    selected_year = int(request.args.get('year', datetime.now().year))  # Default to current year

    # Đếm tổng số sản phẩm, đơn hàng, thành viên, và voucher
    total_products = mongo.db.products.count_documents({})
    total_orders = mongo.db.orders.count_documents({})
    total_users = mongo.db.users.count_documents({})
    total_vouchers = mongo.db.vouchers.count_documents({})

    # Xác định khoảng thời gian dựa trên filter_type và selected_year
    now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    if filter_type == 'week':
        # Lấy tuần đầu tiên của năm
        start_date = datetime(selected_year, 1, 1)
        if start_date.weekday() > 0:  # Nếu không phải thứ Hai, điều chỉnh đến thứ Hai đầu tiên
            start_date += timedelta(days=(7 - start_date.weekday()))
        # Tính ngày kết thúc của năm
        end_date = datetime(selected_year, 12, 31, 23, 59, 59)
    elif filter_type == 'month':
        start_date = datetime(selected_year, 1, 1)
        end_date = datetime(selected_year, 12, 31, 23, 59, 59)
    elif filter_type == 'quarter':
        start_date = datetime(selected_year, 1, 1)
        end_date = datetime(selected_year, 12, 31, 23, 59, 59)
    elif filter_type == 'year':
        start_year = 2020
        end_year = datetime.now().year
        start_date = datetime(start_year, 1, 1)
        end_date = datetime(end_year, 12, 31, 23, 59, 59)
    else:
        raise ValueError("Invalid filter_type. Use 'week', 'month', 'quarter', or 'year'.")

    # Chuyển start_date và end_date thành chuỗi để so sánh với order_date
    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

    # Pipeline để tính doanh thu (không cần tính profit, chỉ cần tổng doanh thu)
    pipeline = [
        # Lọc đơn hàng trong khoảng thời gian
        {
            "$match": {
                "order_date": {
                    "$gte": start_date_str,
                    "$lte": end_date_str
                }
            }
        },
        # Unwind items để tính tổng doanh thu từ mỗi sản phẩm
        {"$unwind": "$items"},
        {
            "$project": {
                "order_date": 1,
                "revenue": {
                    "$multiply": [
                        {"$toDouble": "$items.price"},
                        {"$toInt": "$items.quantity"}
                    ]
                }
            }
        }
    ]

    # Thêm bước nhóm theo filter_type
    if filter_type == "week":
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": {"$dateFromString": {"dateString": "$order_date"}}},
                    "week": {"$week": {"$dateFromString": {"dateString": "$order_date"}}}
                },
                "total_revenue": {"$sum": "$revenue"}
            }
        })
        pipeline.append({"$match": {"_id.year": selected_year}})
        pipeline.append({"$sort": {"_id.week": 1}})

    elif filter_type == "month":
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": {"$dateFromString": {"dateString": "$order_date"}}},
                    "month": {"$month": {"$dateFromString": {"dateString": "$order_date"}}}
                },
                "total_revenue": {"$sum": "$revenue"}
            }
        })
        pipeline.append({"$match": {"_id.year": selected_year}})
        pipeline.append({"$sort": {"_id.month": 1}})

    elif filter_type == "quarter":
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": {"$dateFromString": {"dateString": "$order_date"}}},
                    "quarter": {
                        "$ceil": {
                            "$divide": [
                                {"$month": {"$dateFromString": {"dateString": "$order_date"}}},
                                3
                            ]
                        }
                    }
                },
                "total_revenue": {"$sum": "$revenue"}
            }
        })
        pipeline.append({"$match": {"_id.year": selected_year}})
        pipeline.append({"$sort": {"_id.quarter": 1}})

    elif filter_type == "year":
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": {"$dateFromString": {"dateString": "$order_date"}}}
                },
                "total_revenue": {"$sum": "$revenue"}
            }
        })
        pipeline.append({"$sort": {"_id.year": 1}})

    # Thực thi pipeline
    try:
        revenue_data = list(mongo.db.orders.aggregate(pipeline))
        print(f"Revenue data: {revenue_data}")  # Debug
    except Exception as e:
        print(f"Error in aggregation pipeline: {str(e)}")
        revenue_data = []

    # Chuẩn bị dữ liệu cho biểu đồ
    labels = []
    revenue_values = []

    if filter_type == "week":
        for week in range(1, 53):
            labels.append(f"Week {week}")
            revenue_values.append(0)
        for entry in revenue_data:
            week = entry["_id"]["week"]
            revenue_values[week - 1] = entry["total_revenue"]

    elif filter_type == "month":
        for month in range(1, 13):
            labels.append(month_name[month])
            revenue_values.append(0)
        for entry in revenue_data:
            month = entry["_id"]["month"]
            revenue_values[month - 1] = entry["total_revenue"]

    elif filter_type == "quarter":
        for quarter in range(1, 5):
            labels.append(f"Q{quarter}")
            revenue_values.append(0)
        for entry in revenue_data:
            quarter = entry["_id"]["quarter"]
            revenue_values[quarter - 1] = entry["total_revenue"]

    elif filter_type == "year":
        start_year = 2020
        end_year = datetime.now().year
        for year in range(start_year, end_year + 1):
            labels.append(str(year))
            revenue_values.append(0)
        for entry in revenue_data:
            year = entry["_id"]["year"]
            if start_year <= year <= end_year:
                revenue_values[year - start_year] = entry["total_revenue"]

    # Tạo dictionary chứa các số liệu
    stats = {
        'total_products': total_products,
        'total_orders': total_orders,
        'total_users': total_users,
        'total_vouchers': total_vouchers,
        'revenue_labels': labels,
        'revenue_data': revenue_values,
        'filter_type': filter_type,
        'selected_year': selected_year
    }

    print(f"Stats for dashboard: {stats}")  # Debug
    return render_template('admin/dashboard.html', stats=stats)