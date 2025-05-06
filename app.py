from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text  # For prepared statement queries
from sqlalchemy import create_engine
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fitness.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'caddy'
db = SQLAlchemy(app)

# Set up the engine with a specific isolation level
engine = create_engine('sqlite:///fitness.db', isolation_level="SERIALIZABLE")

# -----------------------------

# Database Models (ORM Implementation)

# -----------------------------

class Instructor(db.Model):  # ORM Model for Instructors
    """
    Represents an instructor in the system.
    Uses SQLAlchemy ORM to map this class to the 'instructors' table.
    """
    __tablename__ = 'instructors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    specialty = db.Column(db.String(100))

class Location(db.Model):  # ORM Model for Locations
    """
    Represents gym locations.
    Mapped to the 'locations' table using SQLAlchemy ORM.
    """
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    gym_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    capacity = db.Column(db.Integer)

class FitnessClass(db.Model):  # ORM Model for Fitness Classes
    """
    Represents a fitness class.
    Uses ORM relationships to link with 'instructors' and 'locations'.
    """
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    scheduled_date = db.Column(db.String(10))  # Format: YYYY-MM-DD
    start_time = db.Column(db.String(5))        # Format: HH:MM
    duration = db.Column(db.Integer)            # Duration in minutes
    instructor_id = db.Column(db.Integer, db.ForeignKey('instructors.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)

    # ORM Relationships (links instructor and location to the class)
    instructor = db.relationship('Instructor', backref=db.backref('classes', lazy=True))
    location = db.relationship('Location', backref=db.backref('classes', lazy=True))

# -----------------------------

# Routes

# -----------------------------

@app.route('/')
def index():
    """List all fitness classes using ORM to query the database."""
    classes = FitnessClass.query.all()  # ORM Query to fetch all classes
    return render_template('index.html', classes=classes)

@app.route('/class/new', methods=['GET', 'POST'])
def new_class():
    """Add a new fitness class with a transaction."""
    if request.method == 'POST':
        # Retrieve form data
        class_name = request.form['class_name']
        description = request.form['description']
        scheduled_date = request.form['scheduled_date']
        start_time = request.form['start_time']
        duration = request.form['duration']
        instructor_id = request.form['instructor']
        location_id = request.form['location']

        # Use a transaction to ensure atomicity
        try:
            with db.session.begin():
                # ORM Insert - Creates a new class instance and adds it to the database
                new_class = FitnessClass(
                    class_name=class_name,
                    description=description,
                    scheduled_date=scheduled_date,
                    start_time=start_time,
                    duration=int(duration),
                    instructor_id=int(instructor_id),
                    location_id=int(location_id)
                )
                db.session.add(new_class)
                db.session.commit()
                flash('New class added successfully!', 'success')
                return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding class: {str(e)}', 'danger')
            return redirect(url_for('new_class'))

    # ORM Query - Fetch instructors and locations for dropdown menus
    instructors = Instructor.query.all()
    locations = Location.query.all()
    return render_template('new_class.html', instructors=instructors, locations=locations)

@app.route('/class/delete/<int:class_id>', methods=['POST'])
def delete_class(class_id):
    """Delete a fitness class by ID using ORM with a transaction."""
    try:
        with db.session.begin():
            class_to_delete = FitnessClass.query.get(class_id)  # ORM Query to fetch class
            if class_to_delete:
                db.session.delete(class_to_delete)  # ORM Delete
                db.session.commit()
                flash('Class deleted successfully!', 'success')
            else:
                flash('Class not found!', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting class: {str(e)}', 'danger')
    return redirect(url_for('index'))

@app.route('/class/edit/<int:class_id>', methods=['GET', 'POST'])
def edit_class(class_id):
    """Edit an existing fitness class with a transaction."""
    fitness_class = FitnessClass.query.get_or_404(class_id)  # ORM Fetch class
    instructors = Instructor.query.all()
    locations = Location.query.all()

    if request.method == 'POST':
        try:
            with db.session.begin():
                # Update class details using ORM
                fitness_class.class_name = request.form['class_name']
                fitness_class.description = request.form['description']
                fitness_class.scheduled_date = request.form['scheduled_date']
                fitness_class.start_time = request.form['start_time']
                fitness_class.duration = int(request.form['duration'])
                fitness_class.instructor_id = int(request.form['instructor'])
                fitness_class.location_id = int(request.form['location'])

                db.session.commit()
                flash('Class updated successfully!', 'success')
                return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')

    return render_template('edit_class.html', fitness_class=fitness_class, instructors=instructors, locations=locations)

@app.route('/report', methods=['GET', 'POST'])
def report():
    """Generate a report of fitness classes using a prepared SQL query."""
    report_data = []
    if request.method == 'POST':
        from_date = request.form['from_date']
        to_date = request.form['to_date']

        # **Prepared Statement Query** to prevent SQL injection
        sql = text("""
            SELECT c.class_name, c.scheduled_date, i.name AS instructor, l.gym_name
            FROM classes c
            JOIN instructors i ON c.instructor_id = i.id
            JOIN locations l ON c.location_id = l.id
            WHERE c.scheduled_date BETWEEN :from_date AND :to_date
            ORDER BY c.scheduled_date
        """)  

        # Execute the prepared statement safely with parameter binding
        with db.session.begin():
            result = db.session.execute(sql, {"from_date": from_date, "to_date": to_date})
            report_data = result.fetchall()

        if not report_data:
            flash("No classes found in the selected date range.", "warning")

    return render_template('report.html', report_data=report_data)

# -----------------------------

# Main Block - Initializes Database

# -----------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # ORM Insert - Insert default instructors and locations if not exists
        if not Instructor.query.filter_by(email='alice@example.com').first():
            instructor1 = Instructor(name='Alice Johnson', email='alice@example.com', specialty='Yoga')
            instructor2 = Instructor(name='Bob Smith', email='bob@example.com', specialty='HIIT')
            location1 = Location(gym_name='Downtown Gym', address='123 Main St', capacity=50)
            location2 = Location(gym_name='Uptown Studio', address='456 Elm St', capacity=30)

            db.session.add_all([instructor1, instructor2, location1, location2])
            db.session.commit()

    app.run(debug=True)