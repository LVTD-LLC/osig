## 1 Dependencies

Install Python dependencies with uv:

```
uv sync
```

Then install JS deps:

```
npm install
```

To get things going, let's try starting the deb frontend server. This will start the css and js complilation and will create a build folder.

```
npm run start
```

## 2 Prepare the files

- Change the `.env.example` file name to `.env`.


## 3 Creating the Database

The next thing you want to do is to create and apply the migrations. First run:

```
uv run python manage.py makemigrations
```

then

```
uv run python manage.py migrate
```

This will create a SQLite database with all the necessary tables.

## 4 Start the dev server

Start by building the frontend resource. You can do that by running:

```
npm run start
```

You should see something like this:

```
webpack 5.73.0 compiled successfully in 3254 ms
```

Note:
Make sure you are running the latest LTS Node.

Now let's start the python server by `uv run python manage.py runserver` in a new terminal window.

---

Et Voila, you should have a basic site running.
