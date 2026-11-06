let sales = [120, 85, 240, 160, 95, 310, 180, 70]
let eligible_sales = sales |> where >= 100 |> map * 0.9 |> sort by item desc
let premium_sales = eligible_sales |> where >= 150
total_revenue = eligible_sales sum item
premium_revenue = premium_sales sum item
average_sale = eligible_sales average item
show "Monthly Sales Report"
show eligible_sales
show premium_sales
show total_revenue
show premium_revenue
show average_sale
