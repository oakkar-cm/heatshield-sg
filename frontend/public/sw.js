/* HeatShield SG service worker — handles web push + notification clicks */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = { title: "HeatShield SG", body: "Heat alert", url: "/" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (e) {}
  const options = {
    body: data.body,
    icon: "/logo192.png",
    badge: "/logo192.png",
    tag: data.tag || "heatshield",
    vibrate: [120, 60, 120],
    data: { url: data.url || "/" },
    requireInteraction: true,
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
