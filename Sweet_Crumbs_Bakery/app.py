import os
import mysql.connector
from flask import (
    Flask,
    render_template,
    session,
    redirect,
    url_for,
    request,
    flash
)

from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector


app = Flask(__name__)

app.secret_key = "sweet-crumbs-development-key"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        ssl_disabled=False
    )


def admin_required():
    return session.get("user", {}).get("is_admin") == 1


# ============================================================
# PRODUCT DATABASE HELPER
# ============================================================

def get_product_by_id(product_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM products WHERE id = %s",
        (product_id,)
    )

    product = cursor.fetchone()

    cursor.close()
    connection.close()

    return product


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# PRODUCTS
# ============================================================

@app.route("/products")
def products():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM products")

    products_list = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "products.html",
        products=products_list
    )


# ============================================================
# PRODUCT DETAILS
# ============================================================

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = get_product_by_id(product_id)

    if product is None:
        return "Product not found", 404

    return render_template(
        "product_detail.html",
        product=product
    )


# ============================================================
# ADD PRODUCT TO CART
# ============================================================

@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = get_product_by_id(product_id)

    if product is None:
        return "Product not found", 404

    cart = session.get("cart", [])

    if not isinstance(cart, list):
        cart = []

    product_id = product["id"]
    product_found = False

    for item in cart:
        if item["id"] == product_id:
            item["quantity"] += 1
            product_found = True
            break

    if not product_found:
        cart.append({
            "id": product["id"],
            "name": product["name"],
            "price": float(product["price"]),
            "image": product.get("image", ""),
            "quantity": 1
        })

    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart"))


# ============================================================
# VIEW CART
# ============================================================

@app.route("/cart")
def cart():
    cart_items = session.get("cart", [])

    if not isinstance(cart_items, list):
        cart_items = []

    total = 0

    for item in cart_items:
        item["subtotal"] = (
            float(item["price"]) * int(item["quantity"])
        )

        total += item["subtotal"]

    return render_template(
        "cart.html",
        cart=cart_items,
        total=total
    )


# ============================================================
# REMOVE PRODUCT FROM CART
# ============================================================

@app.route("/remove-from-cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = session.get("cart", [])

    if not isinstance(cart, list):
        cart = []

    updated_cart = []

    for item in cart:
        if item["id"] != product_id:
            updated_cart.append(item)

    session["cart"] = updated_cart
    session.modified = True

    return redirect(url_for("cart"))


# ============================================================
# CLEAR CART
# ============================================================

@app.route("/clear-cart")
def clear_cart():
    session.pop("cart", None)

    return redirect(url_for("cart"))


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not name or not email or not password or not confirm_password:
            flash("Please complete all fields.")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                flash("An account with that email already exists.")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (%s, %s, %s)
                """,
                (name, email, password_hash)
            )

            conn.commit()

            flash(
                "Account created successfully. "
                "You can now log in."
            )

            return redirect(url_for("login"))

        except mysql.connector.Error as error:
            if conn is not None:
                conn.rollback()

            print("Database error:", error)

            flash(
                "There was a database connection error. "
                "Please make sure MySQL is running and try again."
            )

            return redirect(url_for("register"))

        finally:
            if cursor is not None:
                cursor.close()

            if conn is not None:
                conn.close()

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template(
                "login.html",
                error="Please enter your email and password."
            )

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user is None:
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        if not check_password_hash(user["password"], password):
            return render_template(
                "login.html",
                error="Invalid email or password."
            )

        # Save the user ID for account, checkout,
        # and order-success routes.
        session["user_id"] = user["id"]

        # Save the complete user information.
        session["user"] = {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "is_admin": user.get("is_admin", 0)
        }

        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        return redirect(url_for("account"))

    return render_template("login.html")


# ============================================================
# ACCOUNT
# ============================================================

@app.route("/account")
def account():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM users WHERE id = %s",
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "account.html",
        user=user
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()

    return redirect(url_for("home"))


# ============================================================
# CHECKOUT
# ============================================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cart_items = session.get("cart", [])

    if not isinstance(cart_items, list):
        cart_items = []

    if not cart_items:
        return redirect(url_for("cart"))

    total = 0

    for item in cart_items:
        item["subtotal"] = (
            float(item["price"]) * int(item["quantity"])
        )

        total += item["subtotal"]

    if request.method == "POST":
        payment_method = request.form.get("payment_method", "").strip()

        if not payment_method:
            return render_template(
                "checkout.html",
                cart_items=cart_items,
                total=total,
                error="Please select a payment method."
            )

        customer_name = request.form.get(
            "customer_name",
            session.get("user_name", "")
        ).strip()

        customer_email = request.form.get(
            "customer_email",
            session.get("user_email", "")
        ).strip()

        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not customer_name or not customer_email or not address:
            return render_template(
                "checkout.html",
                cart_items=cart_items,
                total=total,
                error="Please complete all required fields."
            )

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO orders
(
    user_id,
    customer_name,
    customer_email,
    phone,
    address,
    total,
    payment_method,
    status
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                  (
        session["user_id"],
        customer_name,
        customer_email,
        phone,
        address,
        total,
        payment_method,
        "Pending"
    )
)

            order_id = cursor.lastrowid

            for item in cart_items:
                cursor.execute(
                    """
                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        product_name,
                        quantity,
                        price,
                        subtotal
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        item["id"],
                        item["name"],
                        item["quantity"],
                        item["price"],
                        item["subtotal"]
                    )
                )

            connection.commit()

        except mysql.connector.Error as error:
            connection.rollback()
            print("Checkout database error:", error)

            return render_template(
                "checkout.html",
                cart_items=cart_items,
                total=total,
                error="There was a problem placing your order."
            )

        finally:
            cursor.close()
            connection.close()

        session.pop("cart", None)

        session["last_order_id"] = order_id
        session.modified = True

        return redirect(url_for("order_success"))

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total
    )


# ============================================================
# ORDER SUCCESS
# ============================================================

@app.route("/order-success")
def order_success():
    if "user_id" not in session:
        return redirect(url_for("login"))

    order_id = session.get("last_order_id")

    if order_id is None:
        return redirect(url_for("products"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = %s AND user_id = %s
        """,
        (
            order_id,
            session["user_id"]
        )
    )

    order = cursor.fetchone()

    cursor.close()
    connection.close()

    if order is None:
        return redirect(url_for("account"))

    return render_template(
        "order-success.html",
        order=order
    )


# ============================================================
# CONTACT
# ============================================================

@app.route("/contact")
def contact():
    return render_template("contact.html")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        flash(
            "You do not have permission to access "
            "the admin dashboard."
        )

        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                id,
                customer_name,
                customer_email,
                phone,
                address,
                total,
                status,
                created_at
            FROM orders
            ORDER BY created_at DESC
            """
        )

        orders = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    return render_template(
        "admin/dashboard.html",
        orders=orders
    )


# ============================================================
# RUN APPLICATION
# ============================================================

@app.route("/admin/products")
def admin_products():
    if not admin_required():
        flash("You do not have permission to access this page.")
        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, description, price, image, stock
            FROM products
            ORDER BY id DESC
        """)
        products = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "admin/products.html",
        products=products
    )

@app.route("/admin/products/add", methods=["GET", "POST"])
def admin_add_product():
    if not admin_required():
        flash("You do not have permission to access this page.")
        return redirect(url_for("home"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip()
        image = request.form.get("image", "").strip()
        stock = request.form.get("stock", "0").strip()

        if not name or not price:
            flash("Product name and price are required.")
            return redirect(url_for("admin_add_product"))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO products
                (name, description, price, image, stock)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                name,
                description,
                price,
                image,
                stock
            ))

            conn.commit()
            flash("Product added successfully.")
        except Exception as error:
            conn.rollback()
            flash(f"Could not add product: {error}")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin_products"))

    return render_template(
        "admin/product_form.html",
        product=None,
        page_title="Add Product"
    )

@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
def admin_edit_product(product_id):
    if not admin_required():
        flash("You do not have permission to access this page.")
        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, description, price, image, stock
            FROM products
            WHERE id = %s
        """, (product_id,))

        product = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not product:
        flash("Product not found.")
        return redirect(url_for("admin_products"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "0").strip()
        image = request.form.get("image", "").strip()
        stock = request.form.get("stock", "0").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE products
                SET name = %s,
                    description = %s,
                    price = %s,
                    image = %s,
                    stock = %s
                WHERE id = %s
            """, (
                name,
                description,
                price,
                image,
                stock,
                product_id
            ))

            conn.commit()
            flash("Product updated successfully.")
        except Exception as error:
            conn.rollback()
            flash(f"Could not update product: {error}")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("admin_products"))

    return render_template(
        "admin/product_form.html",
        product=product,
        page_title="Edit Product"
    )

@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    if not admin_required():
        flash("You do not have permission to access this page.")
        return redirect(url_for("home"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM products
            WHERE id = %s
        """, (product_id,))

        conn.commit()
        flash("Product deleted successfully.")
    except Exception as error:
        conn.rollback()
        flash(f"Could not delete product: {error}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin_products"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
