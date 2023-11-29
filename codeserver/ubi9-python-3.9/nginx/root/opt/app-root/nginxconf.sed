# Change port
/listen/s%80%8888 default_server%

# Remove listening on IPv6
/\[::\]/d

# Append 8443
/listen 80;/a\
\listen 8443 ssl;

# Add SSL configuration
/server_name/a\
\    listen 443 ssl;\n\
\    ssl_certificate /etc/tls/private/tls.crt;\
\    ssl_certificate_key /etc/tls/private/private-key.key;\n\


# One worker only
/worker_processes/s%auto%1%

s/^user *nginx;//
s%/etc/nginx/conf.d/%/opt/app-root/etc/nginx.d/%
s%/etc/nginx/default.d/%/opt/app-root/etc/nginx.default.d/%
s%/usr/share/nginx/html%/opt/app-root/src%

# See: https://github.com/sclorg/nginx-container/pull/69
/error_page/d
/40x.html/,+1d
/50x.html/,+1d

# Addition for RStudio
/server_name/s%server_name  _%server_name  ${BASE_URL}%
