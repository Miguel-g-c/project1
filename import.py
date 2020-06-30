import csv, os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db     = scoped_session(sessionmaker(bind=engine))

def main():
    # Creating table
    db.execute("CREATE TABLE books (id SERIAL PRIMARY KEY, isbn VARCHAR NOT NULL, title VARCHAR NOT NULL, author VARCHAR NOT NULL, year INTEGER NOT NULL)")

    with open('books.csv', 'r') as bookscsv:
        csvReader = csv.reader(bookscsv)

        # Skip first row
        next(csvReader)

        for isbn, title, author, year in csvReader:
            # Inserting data 
            db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)", {'isbn': isbn, 'title': title, 'author': author, 'year': year})
            print(f"Added '{title}, {author}' to database")

        db.commit()


if __name__ == "__main__":
    main()