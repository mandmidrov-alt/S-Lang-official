import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records_fn_terminal.sl'; out=tmp_path/'records_fn_terminal'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_record_function_sort_reduce(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
total = ordered reduce 0 with acc + item.age
show total
''')
    assert out == ['65']

def test_record_function_sort_sum(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
total = ordered sum row.age
show total
''')
    assert out == ['65']

def test_record_function_sort_average(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age desc
average_age = ordered average row.age
show average_age
''')
    assert out == ['32.5']

def test_record_function_sort_max(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
maximum = ordered max row.age
show maximum
''')
    assert out == ['37']

def test_record_function_sort_min(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
minimum = ordered min row.age
show minimum
''')
    assert out == ['28']

def test_record_function_sort_scalar_projection_then_reduce(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
changed = people map upgrade(row)
ordered = changed sort by row.age asc
ages = ordered map row.age
total = ages reduce 0 with acc + item
show total
''')
    assert out == ['81']
