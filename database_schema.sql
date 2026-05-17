CREATE DATABASE IF NOT EXISTS safe_return;
USE safe_return;

CREATE TABLE IF NOT EXISTS pesticides (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE,
  category VARCHAR(160) NOT NULL,
  danger_level VARCHAR(40) NOT NULL,
  first_aid TEXT NOT NULL,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pesticide_aliases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pesticide_id INT NOT NULL,
  alias VARCHAR(120) NOT NULL,
  FOREIGN KEY (pesticide_id) REFERENCES pesticides(id) ON DELETE CASCADE,
  UNIQUE KEY unique_alias_per_pesticide (pesticide_id, alias)
);

CREATE TABLE IF NOT EXISTS pesticide_symptoms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pesticide_id INT NOT NULL,
  symptom VARCHAR(120) NOT NULL,
  FOREIGN KEY (pesticide_id) REFERENCES pesticides(id) ON DELETE CASCADE,
  UNIQUE KEY unique_symptom_per_pesticide (pesticide_id, symptom)
);

CREATE TABLE IF NOT EXISTS exposure_routes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  pesticide_id INT NOT NULL,
  route VARCHAR(60) NOT NULL,
  FOREIGN KEY (pesticide_id) REFERENCES pesticides(id) ON DELETE CASCADE,
  UNIQUE KEY unique_route_per_pesticide (pesticide_id, route)
);
