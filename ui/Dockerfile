# Build output is served by a minimal nginx static server
FROM cgr.dev/chainguard/nginx:latest

# Copy the compiled project into nginx's default serve directory
COPY --chown=nginx:nginx ./build /usr/share/nginx/html

# Fallback to index.html for client-side routing
RUN printf 'server {\n\
    listen 3000;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/http.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
