import os
import subprocess
from flask import Flask, request, render_template_string, jsonify
import threading
import time

app = Flask(__name__)
data_store = {}

# Страница для ввода данных проекта
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        project_name = request.form.get('project')
        email = request.form.get('email')

        if not project_name or not email:
            return "Ошибка: Пожалуйста, заполните все поля.", 400

        data_store[project_name] = {
            'email': email,
            'status': 'creating',
            'ip_address': None,
            'created_at': time.time(),
            'expires_at': time.time() + 1800  # 30 минут
        }

        threading.Thread(target=deploy_project, args=(project_name,)).start()

        return f'''
            <h1>Проект "{project_name}" создается...</h1>
            <p>Статус: <strong>Создается</strong></p>
            <p>Проверьте статус на странице: <a href="/project-status?project={project_name}">/project-status</a></p>
        '''

    # Отображаем форму для GET-запроса
    return '''
        <h1>Введите данные проекта</h1>
        <form method="POST">
            <label for="project">Имя проекта:</label><br>
            <input type="text" id="project" name="project" required><br><br>
            <label for="email">Email:</label><br>
            <input type="email" id="email" name="email" required><br><br>
            <button type="submit">Создать проект</button>
        </form>
    '''


# Страница для проверки статуса проекта
@app.route('/project-status', methods=['GET'])
def project_status():
    project_name = request.args.get('project')
    if not project_name or project_name not in data_store:
        return "Проект не найден.", 404

    project_data = data_store[project_name]
    status = project_data['status']
    ip_address = project_data.get('ip_address', 'Неизвестно')
    created_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(project_data['created_at']))
    expires_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(project_data['expires_at']))

    return f'''
        <h1>Статус проекта "{project_name}"</h1>
        <p><strong>Статус:</strong> {status}</p>
        <p><strong>IP-адрес:</strong> {ip_address}</p>
        <p><strong>Создан:</strong> {created_at}</p>
        <p><strong>Истекает:</strong> {expires_at}</p>
    '''


# Функция для развертывания проекта
def deploy_project(project_name):
    try:
        terraform_file = "./terraform.tf"
        ansible_playbook = "./nextcloud.yaml"

        if not os.path.exists(terraform_file):
            raise FileNotFoundError(f"Terraform файл не найден: {terraform_file}")
        if not os.path.exists(ansible_playbook):
            raise FileNotFoundError(f"Ansible playbook не найден: {ansible_playbook}")

        print(f"Запуск Terraform для проекта {project_name}...")
        result = subprocess.run(
            ["terraform", "apply", "-auto-approve"],
            cwd=os.path.dirname(terraform_file),
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Ошибка Terraform: {result.stderr}")

        # Извлечение публичного IP из вывода Terraform
        public_ip = None
        for line in result.stdout.splitlines():
            if "public_ip" in line:
                public_ip = line.split("=")[-1].strip()
                break

        if not public_ip:
            raise Exception("Не удалось получить публичный IP из Terraform.")

        # Обновляем данные проекта
        data_store[project_name]['ip_address'] = public_ip
        data_store[project_name]['status'] = 'configuring'

        # Запуск Ansible
        print(f"Запуск Ansible для проекта {project_name}...")
        ansible_inventory = f"{public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa"
        result = subprocess.run(
            ["ansible-playbook", "-i", ansible_inventory, ansible_playbook],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Ошибка Ansible: {result.stderr}")

        # Отправка данных пользователю
        send_email(data_store[project_name]['email'], public_ip)

        # Обновляем статус проекта
        data_store[project_name]['status'] = 'ready'
    except Exception as e:
        print(f"Ошибка при развертывании проекта {project_name}: {e}")
        data_store[project_name]['status'] = 'failed'


# Функция для отправки email
def send_email(email, ip_address):
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(f"Ваш проект готов!\nIP-адрес: {ip_address}\nДоступ к Nextcloud: http://{ip_address}/nextcloud")
    msg['Subject'] = "Данные для доступа к Nextcloud"
    msg['From'] = "your-email@example.com"
    msg['To'] = email

    with smtplib.SMTP('smtp.example.com') as server:
        server.login("your-email@example.com", "your-password")
        server.sendmail("your-email@example.com", [email], msg.as_string())


# Очистка устаревших проектов
def cleanup_projects():
    while True:
        current_time = time.time()
        for project_name, project_data in list(data_store.items()):
            if project_data['expires_at'] < current_time:
                print(f"Удаление проекта {project_name}...")
                del data_store[project_name]
        time.sleep(60)


if __name__ == '__main__':
    threading.Thread(target=cleanup_projects, daemon=True).start()
    app.run(host='0.0.0.0', port=80)