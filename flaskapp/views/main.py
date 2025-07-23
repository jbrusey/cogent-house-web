from flask import Blueprint, render_template

from cogent.base.model import Node, Session

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html', title='Home page')

@main_bp.route('/nodes')
def nodes():
    session = Session()
    try:
        records = session.query(Node.id).all()
    finally:
        session.close()
    return render_template('nodes.html', title='Nodes', nodes=records)
