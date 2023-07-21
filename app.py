from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, RadioField
from wtforms.validators import DataRequired, EqualTo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from random import choice
import requests
from datetime import datetime, timedelta
import pytz


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Secret key for flash messages

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kodland.db'

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

migrate = Migrate(app, db)


# Database models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100), unique=True, nullable=False)
    score = db.Column(db.Integer, default=0)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)
    option1 = db.Column(db.String(200), nullable=False)
    option2 = db.Column(db.String(200), nullable=False)
    option3 = db.Column(db.String(200), nullable=False)
    option4 = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(200), nullable=False)

# Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    nickname = StringField('Nickname', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class QuizForm(FlaskForm):
    question_1 = RadioField('Question 1', choices=[('option1', 'Option 1'), ('option2', 'Option 2'), ('option3', 'Option 3'), ('option4', 'Option 4')], validators=[DataRequired()])
    submit = SubmitField('Submit')


# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if the username and nickname are unique
        existing_username = User.query.filter_by(username=form.username.data).first()
        existing_nickname = User.query.filter_by(nickname=form.nickname.data).first()
        if existing_username:
            flash('Username already exists. Please choose a different username.', 'danger')
        elif existing_nickname:
            flash('Nickname already exists. Please choose a different nickname.', 'danger')
        else:
            user = User(username=form.username.data, password=form.password.data, nickname=form.nickname.data)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)


#User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data, password=form.password.data).first()
        if user:
            login_user(user)  # Login the user using Flask-Login
            return redirect(url_for('index'))
        else:
            flash('Login failed. Please check your username and password.', 'danger')
    return render_template('login.html', form=form)


# Logout 
@app.route('/logout', methods=['GET', 'POST'])
@login_required  # Ensure the user is authenticated before logging out
def logout():
    logout_user()  # Flask-Login's built-in logout function
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))  # Redirect to the login page after logout


# Quiz page
@app.route('/quiz', methods=['GET', 'POST'])
@login_required  # Ensure the user is authenticated before accessing the quiz page
def quiz():
      # get a random question from the database
    random_question = Question.query.order_by(db.func.random()).first()

    # get the user's total score
    total_score = current_user.score

    form = QuizForm()

    return render_template('quiz.html', question=random_question, total_score=total_score, form=form)


# Update the 'submit_quiz' route to check the selected option against the correct option from the database
@app.route('/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    # Get the selected option and question ID from the form
    selected_option = request.form.get('question')
    question_id = request.form.get('question_id')

    # Get the current question from the database using the question ID
    current_question = Question.query.get(int(question_id))

    # Check if the current_question is None (question not found)
    if current_question is None:
        flash('An error occurred while processing your answer. Please try again.', 'danger')
        return redirect(url_for('quiz'))

    # Get the correct option from the current question in the database
    correct_option = current_question.correct_option

    # Update the user's score if the answer is correct
    if selected_option == correct_option:
        current_user.score += 1
        flash('Correct answer!', 'success')
    else:
        flash('Wrong answer!', 'danger')

    db.session.commit()

    return redirect(url_for('quiz'))


# Leaderboard page
@app.route('/leaderboard')
def leaderboard():
    # Get all users ordered by their score in descending order
    users = User.query.order_by(User.score.desc()).all()
    return render_template('leaderboard.html', users=users)


@app.route('/')
def index():
    city = request.args.get('city', 'Istanbul')  # Default city is Istanbul, change if you want
    weather_data = get_weather(city)

    if weather_data:
        # Render the homepage with weather data and dates
        return render_template('index.html', weather_data=weather_data, city_name=city)
    else:
        flash('Weather data not available. Please try again later.', 'warning')
        return render_template('index.html')


def get_weather(city):
    # Get weather information by sending the city name to the API
    api_key = 'f6f2d3b87bbd78fe93926cc1332e7772'  
    url = f'https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric'
    response = requests.get(url)
    data = response.json()

    weather_data = []
    dates_seen = set()

    for forecast in data['list']:
        date_time = datetime.strptime(forecast['dt_txt'], '%Y-%m-%d %H:%M:%S')
        local_timezone = pytz.timezone('Europe/Istanbul')  
        date_time = date_time.replace(tzinfo=pytz.utc).astimezone(local_timezone)
        
        date = date_time.strftime('%Y-%m-%d')

        if date not in dates_seen:
            day = date_time.strftime('%A')
            time = date_time.strftime('%H:%M')

            weather = {
                'day': day,
                'date': date,
                'time': time,
                'day_temp': forecast['main']['temp_max'],
                'night_temp': forecast['main']['temp_min'],
                'description': forecast['weather'][0]['description'],
                'icon': forecast['weather'][0]['icon'],
            }
            weather_data.append(weather)
            dates_seen.add(date)

    return weather_data[:3] 


if __name__ == '__main__':
    app.run(debug=True)
