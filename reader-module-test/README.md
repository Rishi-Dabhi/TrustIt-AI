#### Pre-run

##### Permissions
The machine ingesting the page needs to have access to a sandbox for the headless renderer.
(You can also run it unsandboxed, but you'll have to research that yourself :P )

To test this:
``
and look for the error
`` 

Some operating systems (eg recent Ubuntu) have security policies that mean you have to do this manually

If you have Chrome installed, you can use it's sandbox:
`export CHROME_DEVEL_SANDBOX=/opt/google/chrome/chrome-sandbox`

**Otherwise** you will need to temporarily enable AppArmor unprivileged user namespaces.

```
sudo sysctl kernel.apparmor_restrict_unprivileged_userns=0
sudo sysctl kernel.apparmor_restrict_unprivileged_unconfined=0
```
As this is a security risk, it would be wise to use a custom AppArmor profile to allow only Puppeteer to use namespaces.
You can also set logging from chromium `sudo aa-complain /usr/bin/chromium`.


#### Check out the output:

```
node getPage.js $SOME_NEWSPAGE_URL 

```
```
node getPage.js https://www.theguardian.com/us-news/2025/apr/11/trump-tariffs-china-recession 

```


or 

```
node listen.mjs
```
and in a different window (envvar not required in this window)

```
node getOnePage.js $SOME_NEWSPAGE_URL 

```
```
node getOnePage.js https://www.theguardian.com/us-news/2025/apr/11/trump-tariffs-china-recession 

```