import ast

def check_syntax(filename):
    try:
        with open(filename, 'r') as file:
            source = file.read()
        ast.parse(source)
        print(f"No syntax errors found in {filename}")
    except SyntaxError as e:
        print(f"Syntax error in {filename}: {e}")

check_syntax('main_flask_app.py')