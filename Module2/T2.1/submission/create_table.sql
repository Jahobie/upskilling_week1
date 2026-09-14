CREATE TABLE pageviews AS
    SELECT * FROM read_csv('pageviews.csv');

CREATE TABLE users AS 
    SELECT * FROM read_csv('users.csv')