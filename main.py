"""Main entry point for KubeSight application."""

from kubesight.app import app


def main():
    """Run the Flask application."""
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == "__main__":
    main()
