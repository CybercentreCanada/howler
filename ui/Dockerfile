# Build output is served by a minimal nginx static server
FROM cgr.dev/ssc-spc.gc.ca/nginx:latest

# Copy the compiled project into nginx's default serve directory
COPY --chown=nginx:nginx ./build /usr/share/nginx/html

# Fallback to index.html for client-side routing
COPY --chown=nginx:nginx ./nginx.conf /etc/nginx/http.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
