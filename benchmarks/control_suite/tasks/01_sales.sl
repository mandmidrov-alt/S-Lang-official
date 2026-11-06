data sales:
    A price 10 quantity 3 region 1
    B price 7 quantity 5 region 2
    C price 20 quantity 2 region 1
    D price 4 quantity 10 region 3
    E price 12 quantity 1 region 1

regional = sales where region == 1
values = regional map price * quantity
total = values reduce 0 with acc + item
regional sort by price desc
show regional
show values
show total
