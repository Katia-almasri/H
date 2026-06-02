@echo off
echo ========================================
echo Alembic Database Migration Tool
echo ========================================
echo.

if "%1"=="" goto help
if "%1"=="init" goto init
if "%1"=="create" goto create
if "%1"=="upgrade" goto upgrade
if "%1"=="downgrade" goto downgrade
if "%1"=="current" goto current
if "%1"=="history" goto history
goto help

:init
echo Creating initial migration...
alembic revision --autogenerate -m "Initial migration"
goto end

:create
if "%2"=="" (
    echo ERROR: Please provide a migration message
    echo Usage: migrate.bat create "your message here"
    goto end
)
echo Creating new migration: %2
alembic revision --autogenerate -m %2
goto end

:upgrade
echo Applying all pending migrations...
alembic upgrade head
goto end

:downgrade
echo Rolling back last migration...
alembic downgrade -1
goto end

:current
echo Current database version:
alembic current
goto end

:history
echo Migration history:
alembic history --verbose
goto end

:help
echo Usage:
echo   migrate.bat init              - Create initial migration
echo   migrate.bat create "message"  - Create new migration
echo   migrate.bat upgrade           - Apply all migrations
echo   migrate.bat downgrade         - Rollback last migration
echo   migrate.bat current           - Show current version
echo   migrate.bat history           - Show migration history
echo.
echo Examples:
echo   migrate.bat init
echo   migrate.bat create "Add users table"
echo   migrate.bat upgrade
goto end

:end
echo.
