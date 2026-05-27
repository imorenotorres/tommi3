#!/bin/bash
curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"imts1965@gmail.com","password":"Sol191712@"}'
