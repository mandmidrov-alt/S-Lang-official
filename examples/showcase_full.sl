# S-Lang 1.0 — демонстрационная программа
# Показывает функции, типы, условия, записи, коллекции, конвейер,
# последовательности, состояние, физические величины и графы.

show "=== S-Lang 1.0: LANGUAGE SHOWCASE ==="

# 1. Базовые значения и выражения
let project_name = "Aurora Analytics"
let version = 1.0
let samples = [12, 18, 7, 25, 16, 31, 22]
let enabled = true
let threshold = 15
let doubled_threshold = threshold * 2
let project_status = if enabled then "active" else "inactive"

show "Project:", project_name
show "Version:", version
show "Status:", project_status
show "Threshold x 2:", doubled_threshold

# 2. Функции и ветвление
function classify_score(score: Number) -> Text:
    if score >= 90:
        return "excellent"
    else:
        if score >= 75:
            return "good"
        else:
            if score >= 60:
                return "pass"
            else:
                return "review"

function square(value: Number) -> Number:
    return value * value

function identity<T>(value: T) -> T:
    return value

let score = 86
let score_label = classify_score(score)
let squared_value = square(9)
let generic_number = identity(42)
let generic_text = identity("generic function works")

show "Score classification:", score_label
show "Square of 9:", squared_value
show "Generic values:", generic_number, generic_text

# 3. Записи и доступ к полям
record Employee:
    name: Text
    age: Number
    score: Number

let employee_a = Employee("Alice", 28, 94)
let employee_b = Employee("Boris", 34, 81)
let employee_c = Employee("Clara", 22, 76)

show "Employee A:", employee_a.name, employee_a.age, employee_a.score
show "Employee B:", employee_b.name, employee_b.age, employee_b.score
show "Employee C:", employee_c.name, employee_c.age, employee_c.score

# 4. Фильтрация, преобразование и свёртка коллекции
large_samples = samples where item >= 15
squared_samples = large_samples map item * item
total_squared = squared_samples reduce 0 with acc + item
sample_sum = samples sum
sample_count = samples count
sample_max = samples max

show "All samples:"
show samples
show "Filtered samples:"
show large_samples
show "Squared samples:"
show squared_samples
show "Sum of squared samples:"
show total_squared
show "Sample sum:"
show sample_sum
show "Sample count:"
show sample_count
show "Sample maximum:"
show sample_max

# 5. Табличные данные и сортировка
# Формат строк: data name: затем строки с полями.
data team:
    Alice age 28 score 94
    Boris age 34 score 81
    Clara age 22 score 76
    David age 19 score 63
    Elena age 31 score 89

adults = team where age >= 21
ranked_adults = adults sort by score desc
show "Adult team members:"
show adults
show "Adults ranked by score:"
show ranked_adults

# 6. Конвейер обработки данных
sequence powers from 1 for 8 steps using value * 2
pipeline_result = powers |> where >= 8 |> map item * item |> sum
show "Sequence:"
show powers
show "Pipeline result:"
show pipeline_result

# 7. Последовательность с условием остановки
sequence growth from 1 for up to 8 steps until value >= 100 using value * 3 + 1
show "Growth sequence:"
show growth

# 8. Явно изменяемое состояние
state processed = 0
set processed = processed + 3
show processed

# 9. Физические величины и совместимые единицы
let distance = 120 m
let duration = 10 s
let speed = distance / duration
show "Distance:"
show distance
show "Duration:"
show duration
show "Average speed:"
show speed

# 10. Сущности и вычисляемые свойства
entity Circle:
    radius: m

property Circle.diameter -> m:
    return self.radius * 2

let test_circle = Circle(5 m)
show "Circle radius:"
show test_circle.radius
show "Circle diameter:"
show test_circle.diameter

# 11. Граф маршрутов и поиск пути
graph routes:
    Lab -> Office cost 4
    Office -> Archive cost 3
    Lab -> Workshop cost 2
    Workshop -> Archive cost 8

best_path = find path from Lab to Archive in routes minimizing cost
show "Lowest-cost route:"
show best_path

# 12. Итоговый отчёт
let final_message = if sample_max >= 30 then "high peak detected" else "normal range"
show "=== SUMMARY ==="
show "Project:"
show project_name
show "Samples processed:"
show sample_count
show "Filtered squared total:"
show total_squared
show "Team ranking:"
show ranked_adults
show "Route:"
show best_path
show "Assessment:"
show final_message
show "=== END OF SHOWCASE ==="
