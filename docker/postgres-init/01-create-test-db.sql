-- Separate database for pytest, so tests never touch local development data (spec 10.6).
CREATE DATABASE scrappy_test OWNER scrappy;
