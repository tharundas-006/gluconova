# Gluconova - AI-Powered Non-Invasive Glucometer

Gluconova is a non-invasive glucose monitoring system that uses NIR sensor technology with ESP32 hardware to measure blood glucose levels without finger pricks. The system combines real-time sensor data with an AI-powered web application that provides glucose tracking, food impact prediction, and personalized health insights.

The platform features secure user authentication with JWT tokens, a real-time dashboard displaying current glucose readings and 7-day trend charts, and an AI food impact predictor that estimates glucose spikes based on food input using a glycemic index database. Users can log meals and receive weekly reports showing which foods affect their glucose levels the most, with comparison between predicted and actual impacts.

Additional features include ESP32 sensor simulation for testing, smart alerts for critical glucose levels, trend detection analytics, and personalized dietary recommendations based on user patterns. The system stores all user data in an SQLite database with password encryption via bcrypt.

The backend is built with Flask and provides REST APIs for glucose readings, food logging, and user management. The frontend uses HTML5, CSS3 with Tailwind, and JavaScript with Chart.js for visualizations. The entire project is designed to work with both simulated sensor data and real ESP32 hardware integration, making it suitable for development, testing, and eventual deployment.
