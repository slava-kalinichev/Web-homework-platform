def get_new_submissions(student_name: str) -> list[str] | bool:
    # False если студента не существует или список заданий
    pass

def get_class_grades(class_name: str) -> list[str] | bool:
    # False если класса не существует или список строк, отображающих статистику, с комментариями к ней
    pass

def get_new_tasks(student_login: str) -> list[str]:
    # Список заданий
    pass

def get_assessed_tasks(student_login: str) -> list[str]:
    # Список заданий
    pass

def get_grades(student_login: str) -> dict[str: str]:
    # Словарь задание: оценка, все - строки
    pass