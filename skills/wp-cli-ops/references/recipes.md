# WP-CLI recipes

`(writes)` marks commands that change data. Back up first.

## Orientation

```bash
wp --info
wp core version --extra
wp option get home && wp option get siteurl
wp plugin list --status=active --fields=name,version,update
wp theme list --status=active
wp config list --fields=name,type        # names only, no secret values
wp site list --fields=blog_id,url        # multisite
```

## Database

```bash
wp db export backup-$(date +%Y%m%d-%H%M%S).sql          # add --exclude_tables=wp_actionscheduler_logs to shrink
wp db import backup.sql                                  # (writes) replaces tables in the dump
wp db size --tables --human-readable                    # size per table
wp db query "SELECT COUNT(*) FROM $(wp db prefix)posts WHERE post_type='revision'"
wp db optimize                                           # (writes)
wp core update-db                                        # (writes) after a core update; --network on multisite
```

Clean revisions/trash (writes; review counts first):

```bash
wp post list --post_type=revision --format=count
wp post delete $(wp post list --post_type=revision --format=ids) --force
wp post delete $(wp post list --post_status=trash --format=ids --post_type=any) --force
```

## Cron

```bash
wp cron test                                  # is WP-Cron spawning?
wp cron event list --fields=hook,next_run_relative,recurrence
wp cron event list --format=count
wp cron event run --due-now                   # (writes) run what is overdue
wp cron event delete <hook>                   # (writes) remove a stuck/orphaned event
wp cron schedule list
```

Switch to a real system cron (reliable on low-traffic sites, no request overhead):

```php
// wp-config.php
define( 'DISABLE_WP_CRON', true );
```

```cron
*/5 * * * * cd /var/www/example.com/htdocs && /usr/local/bin/wp cron event run --due-now --quiet
```

Hundreds of overdue events or thousands of events with the same hook usually means
a plugin schedules on every page load; find the hook owner with
`grep -rn "wp_schedule_event\|wp_schedule_single_event" wp-content/plugins/<plugin>`.

## Cache and transients

```bash
wp cache flush                     # (writes) object cache (Redis/Memcached if a drop-in is present)
wp cache type                      # which object cache backend is active
wp transient delete --expired      # (writes)
wp transient delete --all          # (writes) safe but plugins will rebuild them
wp rewrite flush                   # (writes) after changing permalinks/CPTs
wp rewrite list --match=/shop/     # debug a 404
```

Page caches (plugin, Nginx FastCGI, CDN) are separate: purge them with their own tools.

## Updates with a rollback path

```bash
wp db export pre-update.sql
wp plugin list --update=available --fields=name,version,update_version
wp plugin update --all --dry-run
wp plugin update <slug>                                   # (writes) one at a time on production
wp plugin install <slug> --version=1.2.3 --force          # (writes) roll back a plugin
wp core update --minor                                    # (writes) security/maintenance releases
wp core verify-checksums && wp plugin verify-checksums --all   # detect modified core/plugin files
```

## Maintenance mode

```bash
wp maintenance-mode activate      # (writes) shows the core maintenance page
wp maintenance-mode status
wp maintenance-mode deactivate
```

## Users

```bash
wp user list --role=administrator --fields=ID,user_login,user_email
wp user update <id> --user_pass="$(openssl rand -base64 24)" --skip-email   # (writes) then share via a secure channel
wp user session destroy <id> --all                                          # (writes) log out everywhere
wp user create tempadmin tempadmin@example.com --role=administrator          # (writes) delete it afterwards
```

## Debugging a broken site

```bash
wp --skip-plugins --skip-themes plugin list
wp plugin deactivate <slug> --skip-plugins     # (writes) disable the suspect without loading it
wp config set WP_DEBUG true --raw              # (writes) temporary; set back to false
wp config set WP_DEBUG_LOG /var/log/wp-debug.log
wp eval 'var_dump( wp_get_environment_type() );'
wp --debug option get home 2>&1 | tail -20     # see what WP-CLI loads
wp profile stage --all                         # needs: wp package install wp-cli/profile-command
```

## Media

```bash
wp media regenerate 123 --yes                   # (writes) test one attachment first
wp media regenerate --only-missing --yes        # (writes)
wp media image-size
```

## Multisite loops

```bash
for url in $(wp site list --field=url); do
  wp --url="$url" cache flush
done
wp search-replace old.example new.example --network --dry-run
```

## Remote sites

```yaml
# wp-cli.yml in the project
@prod:
  ssh: deploy@example.com/var/www/example.com/htdocs
@staging:
  ssh: deploy@staging.example.com/var/www/staging/htdocs
```

```bash
wp @prod option get home
wp @prod db export - > prod.sql     # stream a dump to your machine
```
