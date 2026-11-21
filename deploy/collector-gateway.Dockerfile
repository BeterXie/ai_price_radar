FROM caddy:2-alpine
# The private gateway binds only 8080. Remove the executable's file capability
# so it can run with an empty capability bounding set and no-new-privileges.
RUN ["setcap", "-r", "/usr/bin/caddy"]
USER 10001:10001
