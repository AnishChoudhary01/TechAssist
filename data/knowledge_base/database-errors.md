# Database connection troubleshooting

## Application cannot connect after a configuration change

Work through these reversible checks before changing production data:

1. Confirm the database process is running and listening on the configured host and port.
2. Compare the application connection string with the database bind address. `localhost` and `127.0.0.1` are not always interchangeable.
3. Verify username, password, and database name in the environment file. Restart the application after editing `.env`.
4. Test with a client from the same machine: `psql`, `mysql`, or a simple TCP check to the port.
5. Check firewall, Docker port publishing, and whether the app runs on the host while the database runs in a container.

## Common error codes

- `ECONNREFUSED`: nothing is listening on that host/port, or the service crashed during startup.
- `ETIMEDOUT`: routing, firewall, or the database is overloaded.
- authentication failed: credentials or default database name do not match.

Do not drop or recreate databases as a first step.
