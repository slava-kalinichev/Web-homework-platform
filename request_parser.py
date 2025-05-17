from database import (
    get_db_connection,
    get_student_id_by_login,
    get_teacher_id_by_login,
    get_student_tasks,
    is_deadline_passed
)


def get_new_submissions(teacher_login: str) -> list[str] | bool:
    """Получает все непроверенные работы для учителя"""
    teacher_id = get_teacher_id_by_login(teacher_login)
    if not teacher_id:
        return False

    cnx = get_db_connection()
    if cnx and cnx.is_connected():
        try:
            cursor = cnx.cursor(dictionary=True)
            cursor.execute('''
                SELECT s.StudentID, s.LastName, s.FirstName, t.TaskID, t.Topic, sub.SubjectTitle, c.ClassTitle
                FROM StudentTasks st
                JOIN Tasks t ON st.TaskID = t.TaskID
                JOIN Students s ON st.StudentID = s.StudentID
                JOIN Subjects sub ON t.SubjectID = sub.SubjectID
                JOIN Classes c ON t.ClassID = c.ClassID
                WHERE t.TeacherID = %s AND st.Status = 'submitted'
                ORDER BY s.LastName, s.FirstName, t.Date DESC
            ''', (teacher_id,))

            tasks = cursor.fetchall()
            cursor.close()

            if not tasks:
                return []

            return [
                f"<b>{task['LastName']} {task['FirstName']}</b> - {task['SubjectTitle']} {task['Topic']} ({task['ClassTitle']})"
                for task in tasks
            ]
        except Exception as e:
            print(f"Ошибка при получении новых работ: {str(e)}")
            return False
        finally:
            if cnx.is_connected():
                cnx.close()
    return False


def get_class_grades(class_name: str, teacher_login: str) -> list[str] | bool:
    """Получает статистику оценок по конкретному классу"""
    teacher_id = get_teacher_id_by_login(teacher_login)
    if not teacher_id:
        return False

    cnx = get_db_connection()
    if cnx and cnx.is_connected():
        try:
            cursor = cnx.cursor(dictionary=True)

            # 1. Проверяем доступ учителя к классу
            cursor.execute('''
                SELECT c.ClassID 
                FROM Classes c
                LEFT JOIN MyClasses mc ON c.ClassID = mc.ClassID AND mc.TeacherID = %s
                LEFT JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
                LEFT JOIN TeachersInSchools tis ON cis.SchoolID = tis.SchoolID AND tis.TeacherID = %s
                WHERE c.ClassTitle = %s AND (mc.TeacherID IS NOT NULL OR tis.TeacherID IS NOT NULL)
            ''', (teacher_id, teacher_id, class_name))

            class_info = cursor.fetchone()
            if not class_info:
                return False

            class_id = class_info['ClassID']

            # 2. Получаем статистику только по заданиям этого класса
            cursor.execute('''
                SELECT 
                    s.StudentID,
                    CONCAT(s.LastName, ' ', s.FirstName) AS student_name,
                    COUNT(CASE WHEN st.Status = 'graded' AND t.ClassID = %s THEN 1 END) AS graded_count,
                    COUNT(CASE WHEN st.Status = 'failed' AND t.ClassID = %s THEN 1 END) AS failed_count,
                    COUNT(CASE WHEN st.Status = 'submitted' AND t.ClassID = %s THEN 1 END) AS submitted_count,
                    AVG(CASE WHEN st.Mark IN ('2','3','4','5') AND t.ClassID = %s THEN CAST(st.Mark AS DECIMAL(10,2)) ELSE NULL END) AS avg_grade
                FROM Students s
                JOIN StudentInClasses sc ON s.StudentID = sc.StudentID AND sc.ClassID = %s
                LEFT JOIN StudentTasks st ON s.StudentID = st.StudentID
                LEFT JOIN Tasks t ON st.TaskID = t.TaskID AND t.ClassID = %s
                GROUP BY s.StudentID
                ORDER BY s.LastName, s.FirstName
            ''', (class_id, class_id, class_id, class_id, class_id, class_id))

            stats = cursor.fetchall()
            cursor.close()

            if not stats:
                return [f"В классе {class_name} пока нет оценок"]

            result = [f"<b>Ведомость оценок класса {class_name}:</b>"]
            for stat in stats:
                result.append(
                    f"<b>{stat['student_name']}</b>:\n"
                    f"Оценки - {stat['graded_count']}, "
                    f"Незачеты - {stat['failed_count']}, "
                    f"На проверке - {stat['submitted_count']}, "
                    f"Средний балл - {round(float(stat['avg_grade']), 2) if stat['avg_grade'] else 'нет'}"
                )

            return result
        except Exception as e:
            print(f"Ошибка при получении статистики оценок: {str(e)}")
            return False
        finally:
            if cnx.is_connected():
                cnx.close()
    return False


def get_new_tasks(student_login: str) -> list[str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return []

    tasks = get_student_tasks(student_id)
    return [
        f"<b>{task['subject']}</b> - {task['theme']} (до {task['deadline']})"
        for task in tasks
        if task['status'] == 'not_submitted' and not is_deadline_passed(task['deadline_unix'])
    ]


def get_assessed_tasks(student_login: str) -> list[str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return []

    tasks = get_student_tasks(student_id)
    return [
        f"<b>{task['subject']}</b> - {task['theme']}: {task['grade']} ({task['comment'] or 'без комментария'})"
        for task in tasks
        if task['status'] == 'graded'
    ]


def get_grades(student_login: str) -> dict[str, str]:
    student_id = get_student_id_by_login(student_login)
    if not student_id:
        return {}

    tasks = get_student_tasks(student_id)
    return {
        f"<b>{task['subject']}</b> - {task['theme']}": task['grade']
        for task in tasks
        if task['grade']
    }