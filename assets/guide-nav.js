(function () {
  const topBar = document.getElementById('readerTopBar');
  const languageSwitch = document.querySelector('.lang-switch');
  if (!topBar) return;
  const useHomepageMotion = document.body.classList.contains('guide-theme');
  const reappearanceDelay = useHomepageMotion ? 1000 : 220;

  // Keep story text clear of the actual navigation at every width.
  if (useHomepageMotion && document.body.classList.contains('article-page')) {
    const syncStoryHeaderHeight = function () {
      document.body.style.setProperty('--story-header-height', topBar.offsetHeight + 'px');
    };
    syncStoryHeaderHeight();
    if (typeof window.ResizeObserver === 'function') {
      new window.ResizeObserver(syncStoryHeaderHeight).observe(topBar);
    } else {
      window.addEventListener('resize', syncStoryHeaderHeight, { passive: true });
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(syncStoryHeaderHeight);
      }
    }
  }

  let scrollStopTimer = null;

  function showTopBar() {
    topBar.classList.remove('reader-hidden-top');
    if (languageSwitch) {
      languageSwitch.classList.remove('reader-hidden-language');
    }
  }

  function hideTopBarWhileScrolling() {
    if (window.scrollY <= 20) {
      showTopBar();
      return;
    }

    topBar.classList.add('reader-hidden-top');
    if (languageSwitch) {
      languageSwitch.classList.add('reader-hidden-language');
    }
  }

  function scheduleTopBarAppearance() {
    window.clearTimeout(scrollStopTimer);
    scrollStopTimer = window.setTimeout(showTopBar, reappearanceDelay);
  }

  function handleScroll() {
    if (!window.matchMedia('(max-width: 1020px)').matches) {
      wakeTopBar();
      return;
    }
    hideTopBarWhileScrolling();
    scheduleTopBarAppearance();
  }

  function wakeTopBar() {
    window.clearTimeout(scrollStopTimer);
    showTopBar();
  }

  topBar.classList.add('reader-auto-hide-target');
  window.addEventListener('scroll', handleScroll, { passive: true });
  if (useHomepageMotion) {
    ['touchstart', 'mousemove', 'keydown', 'resize'].forEach(function (eventName) {
      window.addEventListener(eventName, wakeTopBar, { passive: true });
    });
    ['touchend', 'pointerup', 'scrollend'].forEach(function (eventName) {
      window.addEventListener(eventName, scheduleTopBarAppearance, { passive: true });
    });
  } else {
    window.addEventListener('touchstart', showTopBar, { passive: true });
    window.addEventListener('touchend', showTopBar, { passive: true });
    window.addEventListener('pointerup', showTopBar, { passive: true });
    window.addEventListener('scrollend', showTopBar, { passive: true });
    window.addEventListener('mousemove', showTopBar, { passive: true });
    window.addEventListener('keydown', showTopBar);
    window.addEventListener('resize', wakeTopBar, { passive: true });
  }

  showTopBar();
  })();
