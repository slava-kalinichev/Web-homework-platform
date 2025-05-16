from flask import (Flask, render_template, flash, redirect, url_for,
                   request, session, jsonify, make_response)
from googleapiclient import discovery
from google.oauth2 import service_account
import datetime
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from database import *
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

SCOPES = ['https://www.googleapis.com/auth/calendar']
calendarId = 'viacheslavkalinichev@gmail.com'
SERVICE_ACCOUNT_FILE = 'slava-lms-761d02a60026.json'


class GoogleCalendar(object):
    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.service = discovery.build('calendar', 'v3', credentials=credentials)

    def get_next_class_event(self, class_name):
        now = datetime.utcnow().isoformat() + 'Z'
        t_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'

        # Ищем события с названием "Урок с [название класса]"
        query = f'Урок с {class_name}'

        events_result = self.service.events().list(
            calendarId=calendarId,
            timeMin=now,
            timeMax=t_max,
            q=query,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        if not events:
            return None

        # Возвращаем ближайшее событие
        return events[0]


# Форма входа в приложение
class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
def index():
    loginForm = LoginForm()
    if loginForm.validate_on_submit():
        loginValue = loginForm.username.data
        passValue = loginForm.password.data

        auth_result = authenticate_user(loginValue, passValue)

        if auth_result['status'] == 'success':
            session['user_id'] = loginValue
            session['user_role'] = auth_result['role']

            if auth_result['role'] == 'teacher':
                return redirect(url_for('mainTeacher', user_id=loginValue))
            else:
                return redirect(url_for('mainStudent', user_id=loginValue))
        elif auth_result['status'] == 'login_not_found':
            flash('Несуществующий логин', 'error')
        elif auth_result['status'] == 'wrong_password':
            flash('Неправильный пароль', 'error')
        else:
            flash('Ошибка авторизации', 'error')

    return render_template('index.html', title='Главная страница', form=loginForm)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            data = request.get_json()

            # Проверка обязательных полей
            required_fields = ['lastName', 'firstName', 'role', 'login', 'password']
            if not all(data.get(field) for field in required_fields):
                return jsonify({
                    'success': False,
                    'message': 'Пожалуйста, заполните все обязательные поля'
                }), 400

            # Регистрация пользователя
            user_id = register_user(
                data['lastName'],
                data['firstName'],
                data.get('middleName', ''),
                data['role'],
                data['login'],
                data['password']
            )

            if not user_id:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка регистрации. Логин уже занят.'
                }), 400

            # Для учителей - перенаправляем на дополнительную регистрацию
            if data['role'] == 'teacher':
                session['new_teacher_id'] = user_id
                return jsonify({
                    'success': True,
                    'redirect': url_for('register_teacher', teacher_id=user_id)
                })

            # Для учеников - сразу авторизуем
            session['user_id'] = data['login']
            session['user_role'] = data['role']
            return jsonify({
                'success': True,
                'redirect': url_for('index')
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Ошибка сервера: {str(e)}'
            }), 500

    return render_template('regNewAcc.html', title="Регистрация")


@app.route('/mainTeacher/<user_id>')
def mainTeacher(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    user_info = get_user_info(user_id)
    if not user_info:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))

    teacher_id = get_teacher_id_by_login(user_id)
    if not teacher_id:
        flash('Учитель не найден', 'error')
        return redirect(url_for('index'))

    school = get_teacher_school(teacher_id)
    school_name = school['SchoolName'] if school else None
    is_school_teacher = school is not None

    school_classes = get_school_classes(teacher_id)
    school_classes = sorted(school_classes, key=lambda x: [int(s) if s.isdigit() else s for s in re.split('([0-9]+)', x['name'])])
    my_classes = get_my_classes(teacher_id)
    my_classes = sorted(my_classes, key=lambda x:[int(s) if s.isdigit() else s for s in re.split('([0-9]+)', x['name'])])
    tasks = get_tasks_with_pending_solutions(teacher_id)
    # Получаем статус последней обработанной заявки (если есть)
    last_invitation_status = session.pop('last_invitation_status', None)

    return render_template('mainTeacher.html',
                           title='Личный кабинет учителя',
                           userName=user_info['name'],
                           user_id=user_id,
                           teacher_id=teacher_id,  # Добавляем teacher_id в контекст
                           school_classes=school_classes,
                           my_classes=my_classes,
                           tasks=tasks,
                           school_name=school_name,
                           is_school_teacher=is_school_teacher,
                           last_invitation_status=last_invitation_status)


@app.route('/mainStudent/<user_id>')
def mainStudent(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'student':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    user_info = get_user_info(user_id)
    if not user_info:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))

    # Получаем ID ученика
    student_id = get_student_id_by_login(user_id)
    if not student_id:
        flash('Ошибка загрузки данных ученика', 'error')
        return redirect(url_for('index'))

    tasks = get_student_tasks(student_id)
    pending_invitations = get_pending_invitations(student_id)

    return render_template('mainStudent.html',
                         title='Личный кабинет ученика',
                         userName=user_info['name'],
                         user_id=user_id,
                         tasks=tasks,
                         pending_invitations=pending_invitations)


@app.route('/class_view/<user_id>/<class_name>')
def class_view(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    # Получаем ID класса по имени и teacher_id для проверки владения
    teacher_id = get_teacher_id_by_login(user_id)
    class_info = get_class_by_name_and_teacher(class_name, teacher_id)
    if not class_info:
        flash('Класс не найден или у вас нет к нему доступа', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    students = get_class_students(class_info['id'])

    # Информация об успеваемости для каждого ученика
    students_with_grades = []
    for student in students:
        stats = get_student_class_stats(student['id'], class_info['id'])
        student_dict = dict(student)
        student_dict['average_grade'] = stats['average_grade']
        students_with_grades.append(student_dict)

    return render_template('class_view.html',
                         title=f'Класс {class_name}',
                         user_id=user_id,
                         class_name=class_name,
                         class_id=class_info['id'],
                         students=students_with_grades)


@app.route('/add_student/<user_id>/<class_name>', methods=['GET', 'POST'])
def add_student(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    # Получаем class_id из параметров запроса
    class_id = request.args.get('class_id')
    if not class_id:
        flash('Не указан ID класса', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    # Проверяем, что класс принадлежит учителю
    teacher_id = get_teacher_id_by_login(user_id)
    class_info = get_class_by_id_and_teacher(class_id, teacher_id)
    if not class_info:
        flash('У вас нет доступа к этому классу', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    is_school_class_value = is_school_class(class_id)

    if request.method == 'POST':
        student_login = request.form.get('student_login')
        success, message = add_student_to_class(class_id, student_login, is_school_class_value)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': message}), 400

    return render_template('add_student.html',
                         title='Добавление ученика',
                         user_id=user_id,
                         class_name=class_name,
                         class_info={'id': class_id, 'name': class_name},
                         is_school_class=is_school_class_value)

@app.route('/student_view/<user_id>/<class_name>/<student_id>')
def student_view(user_id, class_name, student_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    # Получаем информацию об ученике
    student_info = get_student_info(student_id)
    if not student_info:
        flash('Ученик не найден', 'error')
        return redirect(url_for('class_view', user_id=user_id, class_name=class_name))

    # Получаем ID класса
    class_info = get_class_by_name(class_name)
    if not class_info:
        flash('Класс не найден', 'error')
        return redirect(url_for('class_view', user_id=user_id, class_name=class_name))

    # Получаем статистику ученика по конкретному классу
    class_stats = get_student_class_stats(student_id, class_info['id'])

    # Формируем полное имя ученика
    full_name = f"{student_info['LastName']} {student_info['FirstName']}"
    if student_info['MiddleName']:
        full_name += f" {student_info['MiddleName']}"

    return render_template('student_view.html',
                         title=f'Ученик {student_info["LastName"]} {student_info["FirstName"][0]}.',
                         user_id=user_id,
                         class_name=class_name,
                         student={
                             'id': student_id,
                             'login': student_info['Login'],
                             'name': full_name
                         },
                         class_stats=class_stats)

@app.route('/delete_student/<user_id>/<class_name>/<student_id>', methods=['POST'])
def delete_student(user_id, class_name, student_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    class_info = get_class_by_name(class_name)
    if not class_info:
        flash('Класс не найден', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    if not delete_student_from_class(class_info['id'], student_id):
        flash('Ошибка при удалении ученика', 'error')

    return redirect(url_for('class_view', user_id=user_id, class_name=class_name))


@app.route('/delete_class/<user_id>/<class_name>')
def delete_class(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    # Получаем class_id из параметров запроса
    class_id = request.args.get('class_id')
    if not class_id:
        flash('Не указан ID класса', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    # Проверяем принадлежность класса учителю
    teacher_id = get_teacher_id_by_login(user_id)
    class_info = get_class_by_id_and_teacher(class_id, teacher_id)
    if not class_info:
        flash('У вас нет прав на удаление этого класса', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    if not delete_class_by_id(class_id, teacher_id):
        flash('Ошибка при удалении класса', 'error')

    return redirect(url_for('mainTeacher', user_id=user_id))


@app.route('/new_task/<user_id>', methods=['GET', 'POST'])
def new_task(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    user_info = get_user_info(user_id)
    if not user_info:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        class_name = request.form.get('class_name')
        subject = request.form.get('subject')
        theme = request.form.get('theme')
        deadline = request.form.get('corrected_deadline')
        task_text = request.form.get('task_text')

        # Обработка файла
        file = request.files.get('file')
        file_data = None
        filename = None
        mime_type = None

        if file and file.filename:
            # Проверка размера файла
            file.seek(0, 2)  # Перемещаемся в конец файла
            file_size = file.tell()
            file.seek(0)  # Возвращаемся в начало

            if file_size > 5 * 1024 * 1024:  # 5MB
                flash('Файл слишком большой. Максимальный размер - 5MB.', 'error')
                return redirect(url_for('new_task', user_id=user_id))

            filename = secure_filename(file.filename)
            file_data = file.read()
            mime_type = file.mimetype

        class_info = get_class_by_name(class_name)
        if not class_info:
            flash('Класс не найден', 'error')
            return redirect(url_for('new_task', user_id=user_id))

        if file_data:
            task_id = create_task_with_file(
                subject_title=subject,
                theme=theme,
                teacher_id=user_info['id'],
                class_id=class_info['id'],
                deadline=deadline,
                task_text=task_text,
                file_data=file_data,
                filename=filename,
                mime_type=mime_type
            )
        else:
            task_id = create_task(
                subject_title=subject,
                theme=theme,
                teacher_id=user_info['id'],
                class_id=class_info['id'],
                deadline=deadline,
                task_text=task_text
            )

        if task_id:
            calendar = GoogleCalendar()
            print("+ - create event\n? - print event list\n")

            #event = calendar.create_event_dict()
            #calendar.create_event(event)

            return redirect(url_for('mainTeacher', user_id=user_id))
        else:
            flash('Ошибка при создании задания', 'error')

    classes = get_teacher_classes_for_select(get_teacher_id_by_login(user_id))
    classes = sorted(classes, key=lambda x: [int(s) if s.isdigit() else s for s in re.split('([0-9]+)', x['name'])])
    return render_template('new_task.html',
                           user_id=user_id,
                           classes=classes)


@app.route('/teacher_task_view/<user_id>/<int:task_id>')
def teacher_task_view(user_id, task_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    task = get_task_details(task_id)
    if not task:
        flash('Задание не найдено', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    solutions = get_task_solutions(task_id)
    return render_template('teacher_task_view.html',
                         title=f'Задание {task["subject"]} - {task["theme"]}',
                         user_id=user_id,
                         task=task,
                         solutions=solutions)

@app.route('/grade_solution/<user_id>/<int:task_id>/<int:student_id>', methods=['GET', 'POST'])
def grade_solution(user_id, task_id, student_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    task = get_task_details(task_id)
    if not task:
        flash('Задание не найдено', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    solution = get_solution_details(task_id, student_id)
    if not solution:
        flash('Решение не найдено', 'error')
        return redirect(url_for('teacher_task_view', user_id=user_id, task_id=task_id))

    # Получаем STID для проверки наличия файла
    stid = get_stid_by_solution(task_id, student_id)
    has_file = get_solution_file(stid) is not None if stid else False

    if request.method == 'POST':
        grade = request.form.get('grade')
        comment = request.form.get('comment', '')

        if grade_solution_func(student_id, task_id, grade, comment):
            return redirect(url_for('teacher_task_view', user_id=user_id, task_id=task_id))
        else:
            flash('Ошибка при сохранении оценки', 'error')

    return render_template('grade_solution.html',
                         title=f'Решение от {solution["student_name"]}',
                         user_id=user_id,
                         task={
                             'id': task_id,
                             'subject': task['subject'],
                             'theme': task['theme'],
                             'text': task['text']
                         },
                         solution=solution,
                         solution_stid=stid,
                         has_file=has_file)


@app.route('/student_task/<user_id>/<int:task_id>', methods=['GET', 'POST'])
def student_task(user_id, task_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'student':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    user_info = get_user_info(user_id)
    if not user_info:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))

    task = get_task_details(task_id)
    if not task:
        flash('Задание не найдено', 'error')
        return redirect(url_for('mainStudent', user_id=user_id))

    task_file = get_task_file(task_id)
    solution = get_solution_details(task_id, user_info['id'])
    is_submitted = solution is not None

    if request.method == 'POST':
        solution_text = request.form.get('solution_text')
        file = request.files.get('file')
        file_data = None
        filename = None
        mime_type = None

        if file and file.filename:
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)

            if file_size > 5 * 1024 * 1024:  # 5MB
                flash('Файл слишком большой. Максимальный размер - 5MB.', 'error')
                return redirect(url_for('student_task', user_id=user_id, task_id=task_id))

            filename = secure_filename(file.filename)
            file_data = file.read()
            mime_type = file.mimetype

        if submit_solution(user_info['id'], task_id, solution_text, file_data, filename, mime_type):
            flash('Решение успешно отправлено!', 'success')
            return redirect(url_for('student_task', user_id=user_id, task_id=task_id))
        else:
            flash('Ошибка при отправке решения', 'error')

    return render_template('student_task.html',
                         title=f'{task["subject"]} - {task["theme"]}',
                         user_id=user_id,
                         task_id=task_id,
                         is_submitted=is_submitted,
                         task=task,
                         solution=solution if is_submitted else {},
                         task_file=task_file)


@app.route('/check_student_login')
def check_student_login():
    login = request.args.get('login')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM Students WHERE Login = ?', (login,))
        exists = cursor.fetchone() is not None
    return jsonify({'exists': exists})


@app.route('/check_class_name')
def check_class_name():
    name = request.args.get('name')
    user_id = session.get('user_id')
    teacher_id = get_teacher_id_by_login(user_id) if user_id else None

    exists = not is_class_name_available(name, teacher_id)
    return jsonify({'exists': exists})

@app.route('/delete_task/<user_id>/<int:task_id>', methods=['POST'])
def delete_task(user_id, task_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    if delete_task_func(task_id):
        flash('Задание успешно удалено', 'success')
    else:
        flash('Ошибка при удалении задания', 'error')

    return redirect(url_for('mainTeacher', user_id=user_id))

@app.route('/teacher_task_statistics/<user_id>/<int:task_id>')
def teacher_task_statistics(user_id, task_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    task = get_task_details(task_id)
    if not task:
        flash('Задание не найдено', 'error')
        return redirect(url_for('mainTeacher', user_id=user_id))

    # Статистика выполнения
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Получаем всех студентов класса
        cursor.execute('''
            SELECT 
                s.StudentID,
                s.LastName,
                s.FirstName,
                s.MiddleName,
                a.Login,
                st.Mark as grade,
                CASE 
                    WHEN st.Mark IS NULL THEN 'not_submitted'
                    WHEN st.Mark = 'незачёт' THEN 'failed'
                    ELSE 'completed'
                END as status
            FROM Students s
            JOIN Accounts a ON s.Login = a.Login
            JOIN StudentInClasses sc ON s.StudentID = sc.StudentID
            JOIN Classes c ON sc.ClassID = c.ClassID
            LEFT JOIN StudentTasks st ON st.StudentID = s.StudentID AND st.TaskID = ?
            WHERE c.ClassTitle = ?
            ORDER BY s.LastName, s.FirstName
        ''', (task_id, task['class_name']))
        students = cursor.fetchall()

        # Считаем статистику
        total = len(students)
        completed = sum(1 for s in students if s['status'] == 'completed')
        failed = sum(1 for s in students if s['status'] == 'failed')
        not_submitted = sum(1 for s in students if s['status'] == 'not_submitted')

    return render_template('teacher_task_statistics.html',
                           title=f'Статистика выполнения {task["subject"]} - {task["theme"]}',
                           user_id=user_id,
                           task=task,
                           students=students,
                           stats={
                               'total': total,
                               'completed': completed,
                               'failed': failed,
                               'not_submitted': not_submitted
                           })

@app.route('/student_data/<user_id>')
def student_data(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'student':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    user_info = get_user_info(user_id)
    if not user_info:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('index'))

    # Получаем данные ученика
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.StudentID, s.LastName, s.FirstName, s.MiddleName, a.Login, a.SecretPass as password
            FROM Students s
            JOIN Accounts a ON s.Login = a.Login
            WHERE s.Login = ?
        ''', (user_id,))
        student_data = cursor.fetchone()

        # Получаем класс ученика
        cursor.execute('''
            SELECT c.ClassTitle 
            FROM StudentInClasses sc
            JOIN Classes c ON sc.ClassID = c.ClassID
            JOIN ClassesInSchools cis ON c.ClassID = cis.ClassID
            WHERE sc.StudentID = ?
        ''', (student_data['StudentID'],))
        school_class = cursor.fetchone()

        # Получаем "мои" классы
        cursor.execute('''
            SELECT c.ClassTitle 
            FROM StudentInClasses sc
            JOIN Classes c ON sc.ClassID = c.ClassID
            JOIN MyClasses mc ON c.ClassID = mc.ClassID
            WHERE sc.StudentID = ? AND NOT EXISTS (
                SELECT 1 FROM ClassesInSchools cis 
                WHERE cis.ClassID = c.ClassID
            )
        ''', (student_data['StudentID'],))
        my_classes = cursor.fetchall()

        # Получаем статистику ученика
        stats = get_student_statistics(student_data['StudentID'])

        return render_template('student_data.html',
                           student=student_data,
                           school_class=school_class['ClassTitle'] if school_class else None,
                           my_classes=', '.join([c['ClassTitle'] for c in my_classes]) if my_classes else None,
                           stats=stats)

@app.context_processor
def utility_processor():
    def check_deadline(deadline_unix):
        if not deadline_unix:
            return False
        try:
            deadline = datetime.fromtimestamp(int(deadline_unix))
            return datetime.now() > deadline
        except:
            return False
    return dict(is_deadline_passed=check_deadline)


@app.route('/register_teacher', methods=['GET', 'POST'])
def register_teacher():
    if request.method == 'GET':
        # получаем данные учителя из сессии
        teacher_id = session.get('new_teacher_id')
        if not teacher_id:
            return redirect(url_for('register'))

        teacher = get_teacher_info_by_id(teacher_id)
        return render_template('register_teacher.html',
                               last_name=teacher['LastName'],
                               first_name=teacher['FirstName'],
                               middle_name=teacher['MiddleName'],
                               teacher_id=teacher_id)

    if request.method == 'POST':
        data = request.get_json()
        teacher_id = data['teacher_id']
        access_type = data['accessType']
        school_code = data.get('schoolCode')

        if access_type == 'full' and not school_code:
            return jsonify({'success': False, 'message': 'Введите код школы'})

        # Проверяем код школы
        school_id = None
        if access_type == 'full':
            school = get_school_by_code(school_code)
            if not school:
                return jsonify({'success': False, 'message': 'Несуществующий код доступа школы'}), 400
            school_id = school['SchoolID']

        # Сохраняем связь учитель-школа
        if school_id:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO TeachersInSchools (SchoolID, TeacherID)
                    VALUES (?, ?)
                ''', (school_id, teacher_id))
                conn.commit()

        # флаг доступа в сессии
        session['teacher_access_type'] = access_type
        return jsonify({'success': True})


# Для школьных классов
@app.route('/new_school_class/<user_id>', methods=['GET', 'POST'])
def new_school_class(user_id):
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        teacher_id = get_teacher_id_by_login(user_id)

        if create_class(class_name, teacher_id, is_school_class=True):
            flash('Школьный класс создан!', 'success')
            return redirect(url_for('mainTeacher', user_id=user_id))
        else:
            flash('Ошибка создания класса', 'error')

    return render_template('newSchoolClass.html',
                           title='Добавление школьного класса',
                           user_id=user_id)


# Для персональных классов
@app.route('/new_my_class/<user_id>', methods=['GET', 'POST'])
def new_my_class(user_id):
    if request.method == 'POST':
        class_name = request.form.get('class_name')
        teacher_id = get_teacher_id_by_login(user_id)

        if create_my_class(class_name, teacher_id):
            flash('Персональный класс создан!', 'success')
            return redirect(url_for('mainTeacher', user_id=user_id))
        else:
            flash('Ошибка создания класса', 'error')

    return render_template('newMyClass.html',
                           title='Добавление моего класса',
                           user_id=user_id)


@app.route('/check_student_for_class')
def check_student_for_class():
    login = request.args.get('login')
    class_id = request.args.get('class_id')
    is_school = request.args.get('is_school', '').lower() == 'true'

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Проверяем существует ли ученик
        cursor.execute('SELECT StudentID FROM Students WHERE Login = ?', (login,))
        student = cursor.fetchone()

        if not student:
            return jsonify({
                'can_add': False,
                'message': 'Ученик с таким логином не найден'
            })

        # Проверяем не состоит ли уже в этом классе
        cursor.execute('''
            SELECT 1 FROM StudentInClasses 
            WHERE ClassID = ? AND StudentID = ?
        ''', (class_id, student['StudentID']))

        if cursor.fetchone():
            return jsonify({
                'can_add': False,
                'message': 'Ученик уже состоит в этом классе'
            })

        # Для школьных классов проверяем не состоит ли в другом школьном классе
        if is_school:
            cursor.execute('''
                SELECT 1 FROM StudentInClasses sc
                JOIN ClassesInSchools cis ON sc.ClassID = cis.ClassID
                WHERE sc.StudentID = ? AND sc.ClassID != ?
            ''', (student['StudentID'], class_id))

            if cursor.fetchone():
                return jsonify({
                    'can_add': False,
                    'message': 'Ученик уже состоит в другом школьном классе'
                })

    return jsonify({
        'can_add': True,
        'message': ''
    })


@app.route('/send_invitation/<user_id>/<class_name>', methods=['POST'])
def send_invitation(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        return jsonify({'success': False, 'message': 'Сессия завершена'}), 403

    student_login = request.form.get('student_login')
    class_id = request.form.get('class_id')
    is_school_class_value = is_school_class(class_id)

    # Получаем teacher_id из базы данных по логину учителя
    teacher_id = get_teacher_id_by_login(user_id)

    if not teacher_id:
        return jsonify({'success': False, 'message': 'Учитель не найден'})

    # Получаем имя ученика для сообщения
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT LastName, FirstName FROM Students 
            WHERE Login = ?
        ''', (student_login,))
        student = cursor.fetchone()

    if not student:
        return jsonify({'success': False, 'message': 'Ученик не найден'})

    student_name = f"{student['LastName']} {student['FirstName'][0]}."

    success, message = send_class_invitation(class_id, student_login, teacher_id, is_school_class_value)
    return jsonify({
        'success': success,
        'message': message,
        'student_name': student_name
    })


@app.route('/process_invitation/<user_id>', methods=['POST'])
def handle_invitation(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'student':
        return jsonify({'success': False, 'message': 'Сессия завершена'}), 403

    data = request.get_json()
    invitation_id = data.get('invitation_id')
    action = data.get('action')

    success, result = process_invitation_func(invitation_id, action)

    if success:
        # Сохраняем информацию для показа учителю
        teacher_id = result['teacher_id']
        session['last_invitation_status'] = {
            'class_name': result['class_name'],
            'student_name': result['student_name'],
            'status': result['status']
        }
        return jsonify({'success': True, 'message': 'Заявка обработана'})
    else:
        return jsonify({'success': False, 'message': result})


@app.route('/student_class_view/<user_id>/<class_name>')
def student_class_view(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id:
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    # Получаем данные ученика
    student_id = get_student_id_by_login(user_id)
    if not student_id:
        flash('Ученик не найден', 'error')
        return redirect(url_for('index'))

    student = get_student_info(student_id)
    if not student:
        flash('Ученик не найден', 'error')
        return redirect(url_for('index'))

    # Получаем информацию о классе
    class_info = get_class_by_name(class_name)
    if not class_info:
        flash('Класс не найден', 'error')
        return redirect(url_for('student_data', user_id=user_id))

    # Получаем учителя-владельца класса
    teacher = get_class_teacher(class_info['id'])

    # Получаем статистику по классу
    stats = get_student_class_stats(student_id, class_info['id'])

    return render_template('student_class_view.html',
                           title=f'Мой класс {class_name}',
                           user_id=user_id,
                           class_name=class_name,
                           teacher=teacher,
                           stats=stats)


@app.route('/leave_class/<user_id>/<class_name>', methods=['POST'])
def leave_class(user_id, class_name):
    if 'user_id' not in session or session['user_id'] != user_id:
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    student_id = get_student_id_by_login(user_id)
    class_info = get_class_by_name(class_name)

    if student_id and class_info:
        if delete_student_from_class(class_info['id'], student_id):
            flash(f'Вы покинули класс {class_name}', 'success')
        else:
            flash('Ошибка при выходе из класса', 'error')

    return redirect(url_for('student_data', user_id=user_id))

@app.route('/download_task_file/<int:task_id>')
def download_task_file(task_id):
    # Скачивание прикрепленного файла решения
    if 'user_id' not in session:
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    file_data = get_task_file(task_id)
    if not file_data:
        flash('Файл не найден', 'error')
        return redirect(url_for('index'))

    response = make_response(file_data['FileData'])
    response.headers['Content-Type'] = file_data['MimeType']
    response.headers['Content-Disposition'] = f'attachment; filename={file_data["FileName"]}'
    return response

@app.route('/download_solution_file/<int:stid>')
def download_solution_file(stid):
    # Скачивание прикрепленного файла решения
    if 'user_id' not in session or session['user_role'] != 'teacher':
        flash('Сессия завершена', 'error')
        return redirect(url_for('index'))

    file_data = get_solution_file(stid)
    if not file_data:
        flash('Файл не найден', 'error')
        return redirect(url_for('index'))

    response = make_response(file_data['FileData'])
    response.headers['Content-Type'] = file_data['MimeType']
    response.headers['Content-Disposition'] = f'attachment; filename={file_data["FileName"]}'
    return response


@app.route('/leave_school', methods=['POST'])
def handle_leave_school():
    if request.method == 'POST':
        teacher_id = request.json.get('teacher_id')
        success, message = leave_school(teacher_id)
        return jsonify({'success': success, 'message': message})

@app.route('/join_school', methods=['POST'])
def handle_join_school():
    if request.method == 'POST':
        teacher_id = request.json.get('teacher_id')
        school_code = request.json.get('school_code')
        success, message = join_school(teacher_id, school_code)
        return jsonify({'success': success, 'message': message})


@app.route('/get_next_class_date/<user_id>', methods=['POST'])
def get_next_class_date(user_id):
    if 'user_id' not in session or session['user_id'] != user_id or session['user_role'] != 'teacher':
        return jsonify({'success': False, 'message': 'Сессия завершена'}), 403

    data = request.get_json()
    class_name = data.get('class_name')

    if not class_name:
        return jsonify({'success': False, 'message': 'Выберите класс'})

    calendar = GoogleCalendar()
    event = calendar.get_next_class_event(class_name)

    if not event:
        return jsonify({'success': False, 'message': f'В ближайшее время нет уроков с {class_name}'})

    # Извлекаем дату из события и форматируем её
    start_date = event['start'].get('dateTime', event['start'].get('date'))
    event_date = datetime.fromisoformat(start_date).date()

    return jsonify({
        'success': True,
        'date': event_date.isoformat()
    })

if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')