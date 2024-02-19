from flask import Flask, render_template, request, redirect, url_for, session, flash
from neo4j import GraphDatabase

app = Flask(__name__, static_folder="static")
app.secret_key = "qRt9pL2sF7gY3wX8zA6c"

NEO4J_URI = "YOUR_URI"
NEO4J_USER = "YOUR_USERNAME"
NEO4J_PASSWORD = "YOUR_PASSWORD"

locations_called = {}


class Neo4jDB:
    def __init__(self, uri, user, password):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )

    def close(self):
        self._driver.close()

    def delete_itinerary(self, username, location_id):
        with self._driver.session() as session:
            session.execute_write(self._delete_itinerary, username, location_id)

    def delete_itinerary_attractions(self, username, location_id):
        with self._driver.session() as session:
            session.execute_write(
                self._delete_itinerary_attractions, username, location_id
            )

    def _delete_itinerary(self, tx, username, location_id):
        query = f"""
        MATCH  (u:User {{username: '{username}'}})-[r:Restaurant_link {{id: '{location_id}'}}]->(i:Itinerary)
        DELETE r
        """
        tx.run(query, username=username, location_id=location_id)

    def _delete_itinerary_attractions(self, tx, username, location_id):
        query = f"""
        MATCH  (u:User {{username: '{username}'}})-[r:Attraction_link {{id: '{location_id}'}}]->(i:Itinerary)
        DELETE r
        """
        tx.run(query, username=username, location_id=location_id)

    def create_user(self, username, password):
        with self._driver.session() as session:
            session.execute_write(self._create_user, username, password)

    def _create_user(self, tx, username, password):
        query = "CREATE (u:User {username: $username, password: $password})"
        tx.run(query, username=username, password=password)

    def get_user(self, username):
        with self._driver.session() as session:
            return session.execute_read(self._get_user, username)

    def _get_user(self, tx, username):
        query = "MATCH (u:User {username: $username}) RETURN u"
        result = tx.run(query, username=username)
        return result.single()

    def create_itinerary(self, username, location):
        with self._driver.session() as session:
            session.execute_write(
                self._create_itinerary_attractions, username, location
            )
            session.execute_write(
                self._create_itinerary_restaurants, username, location
            )

    def _create_itinerary_attractions(self, tx, username, location):
        query = f"""
        MATCH (c:Primary_city {{city_name: '{location}'}})<-[:is_in]-(z:ZipCode)-[:has_attraction]->(r:Attraction)
        WITH r
        ORDER BY r.average_rating DESC
        LIMIT 5
        
        MATCH (u:User {{username: '{username}'}})
        MERGE (u)-[:Attraction_link{{id:'{location}'}}]->(i:Itinerary)
        WITH r, i
        CREATE (i)-[:itinerary_attraction]->(r)
        RETURN i"""
        tx.run(query, username=username, location=location)

    def _create_itinerary_restaurants(self, tx, username, location):
        query = f"""
            MATCH (c:Primary_city  {{city_name: '{location}'}})<-[:is_in]-(z:ZipCode)-[:has_restaurant]->(r:Restaurant)
            WITH r
            ORDER BY r.average_rating DESC
            LIMIT 10

            MATCH (u:User {{username: '{username}'}})
            MERGE (u)-[:Restaurant_link{{id:'{location}'}}]->(i:Itinerary)
            WITH r, i
            CREATE (i)-[:itinerary_restaurant]->(r)
            RETURN i"""
        tx.run(query, username=username, location=location)

    def get_restaurant_suggestions(self, zipcode):
        with self._driver.session() as session:
            return session.execute_read(self._get_restaurant_suggestions, zipcode)

    def _get_restaurant_suggestions(self, tx, location_name):
        query = f"""
                MATCH (c:Primary_city {{city_name: '{location_name}'}})<-[:is_in]-(z:ZipCode)-[:has_restaurant]->(r:Restaurant)
                RETURN r.restaurant_name, r.average_rating, r.restaurant_address, r.url,r.price_level, r.Main_cuisine
                ORDER BY r.average_rating DESC
                LIMIT 10
            """

        result = tx.run(query, location_name=location_name)
        return result.data()

    def get_similar_locations(self, zipcode):
        with self._driver.session() as session:
            return session.execute_read(self._get_similar_locations, zipcode)

    def _get_similar_locations(self, tx, location_name):
        query = f"""
                MATCH (c:Primary_city {{city_name: '{location_name}'}})<-[:is_in]-(z:ZipCode)-[:has_attraction]->(r:Attraction)
                RETURN r.attraction_name, r.attraction_rating, r.attraction_address, r.attraction_url,r.top_review, r.description
                ORDER BY r.attraction_rating DESC
                LIMIT 5
            """

        result = tx.run(query, location_name=location_name)
        return result.data()

    def update_user_review(self, restaurant_name, user_review):
        print(restaurant_name, user_review)
        with self._driver.session() as session:
            session.execute_write(
                self._update_user_review, restaurant_name, user_review
            )

    def _update_user_review(self, tx, restaurant_name, user_review):
        query = f"""
        MATCH (r:Restaurant {{restaurant_name: '{restaurant_name}'}})
        SET r.user_review = '{user_review}'
        RETURN r
        """
        result = tx.run(query, restaurant_name=restaurant_name, user_review=user_review)
        return result.data()

    def get_user_past_itineraries_attractions(self, username):
        with self._driver.session() as session:
            return session.execute_read(
                self._get_user_past_itineraries_attractions, username
            )

    def get_user_past_itineraries_restaurants(self, username):
        with self._driver.session() as session:
            return session.execute_read(
                self._get_user_past_itineraries_restaurants, username
            )

    def _get_user_past_itineraries_attractions(self, tx, username):
        query = f"""
        match (u:User{{username: '{username}'}}) -[link:Attraction_link] ->(i:Itinerary)- [:itinerary_attraction] ->(r:Attraction) return 
                         link.id, r.attraction_name, r.attraction_rating, r.attraction_address, r.attraction_url, r.description LIMIT 5
        """
        result = tx.run(query, username=username)
        return result.data()

    def _get_user_past_itineraries_restaurants(self, tx, username):
        query = f"""
        match (u:User{{username: '{username}'}}) -[link:Restaurant_link] ->(i:Itinerary)- [:itinerary_restaurant] ->(r:Restaurant)
                            return link.id, r.restaurant_name, r.Main_cuisine,r.average_rating, r.restaurant_address, r.url, r.price_level LIMIT 5
        """
        print(query)
        result = tx.run(query, username=username)
        print(result)
        return result.data()

    def get_similar_restaurants(
        self, location_name, cr_name, selected_location, search_CR
    ):
        with self._driver.session() as session:
            return session.execute_read(
                self._get_similar_restaurants,
                location_name,
                cr_name,
                selected_location,
                search_CR,
            )

    def _get_similar_restaurants(
        self, tx, location_name, cr_name, selected_location, search_CR
    ):
        query = """"""
        if selected_location == "city" and search_CR == "cuisine":
            query = f"""
                MATCH (c:Primary_city {{city_name: '{location_name}'}})<-[:is_in]-(z:ZipCode)-[:has_restaurant]->(r:Restaurant)
                WHERE r.Main_cuisine = '{cr_name}' OR r.cuisine2 = '{cr_name}' OR r.cuisine3 = '{cr_name}'
                RETURN r.restaurant_name, r.Main_cuisine,r.average_rating, r.restaurant_address, r.url, r.price_level, r.user_review
                ORDER BY r.average_rating DESC
                LIMIT 5
            """

        elif selected_location == "city" and search_CR == "restaurants":
            query = f"""MATCH (city:Primary_city {{city_name: '{location_name}'}})
                    MATCH (other_restaurant:Restaurant {{restaurant_name: '{cr_name}'}})
                    WITH city, other_restaurant
                    MATCH (r:Restaurant)-[:restaurant_present_in]->(z3:ZipCode)-[:is_in]->(city)
                    WHERE r.Main_cuisine = other_restaurant.Main_cuisine OR r.cuisine2 = other_restaurant.Main_cuisine OR r.cuisine3 = other_restaurant.Main_cuisine and other_restaurant <> r
                    RETURN r.restaurant_name, r.Main_cuisine,r.average_rating, r.restaurant_address, r.url,r.price_level,r.user_review
                    ORDER BY r.average_rating DESC
                    LIMIT 5"""
            # query = f"""MATCH (a:Attraction {{attraction_name: '{location_name}'}}) -[:attraction_present_in]->(z2:ZipCode)-[:is_in]->(c:Primary_city) <-[:is_in]-(z:ZipCode)-[:has_restaurant]->(r:Restaurant)
            #         WHERE r.Main_cuisine = '{cr_name}' OR r.cuisine2 = '{cr_name}' OR r.cuisine3 = '{cr_name}'
            #         RETURN r.restaurant_name, r.average_rating, r.restaurant_address, r.url,r.price_level
            #         ORDER BY r.average_rating DESC
            #         LIMIT 5"""

        elif selected_location == "attraction" and search_CR == "cuisine":
            query = f"""MATCH (a:Attraction {{attraction_name: '{location_name}'}}) -[:attraction_present_in]->(z2:ZipCode)-[:is_in]->(c:Primary_city) <-[:is_in]-(z:ZipCode)-[:has_restaurant]->(r:Restaurant)
                    WHERE r.Main_cuisine = '{cr_name}' OR r.cuisine2 = '{cr_name}' OR r.cuisine3 = '{cr_name}'
                    RETURN r.restaurant_name, r.Main_cuisine,r.average_rating, r.restaurant_address, r.url,r.price_level,r.user_review
                    ORDER BY r.average_rating DESC
                    LIMIT 5"""
        elif selected_location == "attraction" and search_CR == "restaurants":
            query = f"""MATCH (attraction:Attraction {{attraction_name: '{location_name}'}})<-[:has_attraction]-(z:ZipCode)<-[:has_code]-(city:Primary_city)
                        MATCH (other_restaurant:Restaurant {{restaurant_name: '{cr_name}'}})
                     WITH city, other_restaurant
                    MATCH (r:Restaurant)-[:restaurant_present_in]->(z3:ZipCode)-[:is_in]->(city)
                    WHERE r.Main_cuisine = other_restaurant.Main_cuisine OR r.cuisine2 = other_restaurant.Main_cuisine OR r.cuisine3 = other_restaurant.Main_cuisine and other_restaurant <> r
                    RETURN r.restaurant_name, r.Main_cuisine,r.average_rating, r.restaurant_address, r.url,r.price_level,r.user_review
                    ORDER BY r.average_rating DESC
                    LIMIT 5"""
        elif selected_location == "attraction" and search_CR == "cuisine":
            query = f"""MATCH (attraction:Attraction {{attraction_name: '{location_name}'}})<-[:has_attraction]-(z:ZipCode)<-[:has_code]-(city:Primary_city)
                        WITH city
                        MATCH (other_restaurant:Restaurant)-[:restaurant_present_in]->(z3:ZipCode)-[:is_in]->(city)
                        WHERE other_restaurant.Main_cuisine = '{cr_name}' OR other_restaurant.cuisine2 = '{cr_name}' OR other_restaurant.cuisine3 = '{cr_name}'
                        RETURN other_restaurant.restaurant_name, other_restaurant.Main_cuisine,other_restaurant.average_rating, other_restaurant.restaurant_address, other_restaurant.url,other_restaurant.price_level,other_restaurant.user_review
                        ORDER BY other_restaurant.average_rating DESC
                        LIMIT 5
                        """
        print("query", query)
        result = tx.run(
            query,
            location_name=location_name,
            cr_name=cr_name,
            selected_location=selected_location,
            search_CR=search_CR,
        )
        # print(result.data())
        return result.data()


neo4j_db = Neo4jDB(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    user = neo4j_db.get_user(username)

    if user and user["u"]["password"] == password:
        session["username"] = username
        return redirect(url_for("front"))
    else:
        return "Invalid login credentials"


@app.route("/signup", methods=["POST"])
def signup():
    username = request.form["fullname"]
    password = request.form["password"]
    neo4j_db.create_user(username, password)
    return redirect(url_for("front"))


@app.route("/front")
def front():
    if "username" in session:
        return render_template("front.html")
    else:
        return redirect(url_for("index"))


# @app.route('/dashboard')
# def dashboard():
#     name = session.get('fullname')
#     print(name)
#     if 'username' in session:
#         user = neo4j_db.get_user(name)
#         return render_template('dashboard.html', user=user)  # Pass the 'user' variable to the template
#     else:
#         flash('Please log in to access the dashboard.', 'error')
#         return redirect(url_for('index'))


@app.route("/new_itinerary", methods=["GET", "POST"])
def new_itinerary():
    username = session.get("username")

    if not username:
        flash("Please log in to create a new itinerary.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        location = request.form["location"]
        if location not in locations_called:
            locations_called[location] = 1

        neo4j_db.create_itinerary(username, location)
        similar_locations = neo4j_db.get_similar_locations(location)
        suggest_restaurants = neo4j_db.get_restaurant_suggestions(location)
        # print(suggest_restaurants, similar_locations)
        return render_template(
            "results.html",
            results1=similar_locations,
            results2=suggest_restaurants,
            category="Locations",
        )

    return render_template("new_itinerary.html")


@app.route("/past_itineraries")
def past_itineraries():
    username = session.get("username")

    if not username:
        flash("Please log in to access past itineraries.", "error")
        return redirect(url_for("index"))

    past_attractions = neo4j_db.get_user_past_itineraries_attractions(username)
    past_restaurants = neo4j_db.get_user_past_itineraries_restaurants(username)
    loc = ""
    if len(past_attractions) > 0:
        loc = past_attractions[0]["link.id"]
    print(past_restaurants)
    return render_template(
        "past_itineraries.html",
        past_attractions=past_attractions,
        past_restaurants=past_restaurants,
        location=loc,
    )


@app.route("/submit_review", methods=["POST"])
def submit_review():
    restaurant_name = request.form["restaurant_name"]
    user_review = request.form["user_review"]
    neo4j_db.update_user_review(restaurant_name, user_review)
    return redirect(url_for("restaurants"))


@app.route("/restaurants", methods=["GET", "POST"])
def restaurants():
    username = session.get("username")
    selected_option = None

    if not username:
        flash("Please log in to access restaurant recommendations.", "error")
        return redirect(url_for("index"))

    # if request.method == 'POST':
    #     location_name = request.form['location_name']
    #     cuisine = request.form['cuisine']

    if request.method == "POST":
        location_name = request.form["location_name"]
        cr_name = request.form["cr_name"]
        selected_option = request.form["search_option"]
        search_CR = request.form["search_CR"]
        print(selected_option, search_CR)
        print(location_name, cr_name)
        # Call the Neo4j function to get similar restaurants
        similar_restaurants = neo4j_db.get_similar_restaurants(
            location_name, cr_name, selected_option, search_CR
        )
        print(similar_restaurants)
        return render_template(
            "restaurants.html", similar_restaurants=similar_restaurants
        )

    return render_template("restaurants.html", similar_restaurants=[])


@app.route("/delete_itinerary/<location_id>", methods=["DELETE"])
def delete_itinerary(location_id):
    username = session.get("username")
    neo4j_db.delete_itinerary(username, location_id)
    neo4j_db.delete_itinerary_attractions(username, location_id)


if __name__ == "__main__":
    app.run(debug=True, port=5003)
