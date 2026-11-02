import pytest

from tools import calculator, page_find, python_exec, web_search

WC = "Чемпионат мира по футболу 2026"


# calculator
def test_calculator_normal():
    assert calculator("17*23+5") == "396"

def test_calculator_empty():
    assert calculator("").startswith("ошибка вычисления")

def test_calculator_error():
    assert "ошибка" in calculator("__import__('os')")      # опасный код не выполняется


# python_exec
def test_python_exec_normal():
    assert python_exec("print(sum(range(10)))") == "45"

def test_python_exec_empty():
    assert python_exec("x = 1") == "Код исполнился, но ничего не напечатал"

def test_python_exec_error():
    assert "ZeroDivisionError" in python_exec("1/0")


# web_search
def test_web_search_normal():
    assert web_search("Scott Derrickson").startswith("[Scott Derrickson]")

def test_web_search_empty():
    assert web_search("qwxzv 1234567 nonsense") == "nothing found"

def test_web_search_error():
    with pytest.raises(ValueError):                      
        web_search("Scott Derrickson", lang="de")


# page_find
def test_page_find_normal():
    out = page_find(WC, ["финал", "Испания", "Аргентина"], lang="ru")
    assert "Торрес" in out                                

def test_page_find_empty():
    assert "нет строк" in page_find(WC, ["квиддич", "снитч"], lang="ru")

def test_page_find_error():
    assert page_find("Qwxzv nonexistent page 12345", ["x"]).startswith("no such page")
