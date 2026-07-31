(function () {
  const topBar = document.getElementById('readerTopBar');
  const languageSwitch = document.querySelector('.lang-switch');
  if (!topBar) return;

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

  function handleScroll() {
    hideTopBarWhileScrolling();
    window.clearTimeout(scrollStopTimer);
    scrollStopTimer = window.setTimeout(showTopBar, 220);
  }

  topBar.classList.add('reader-auto-hide-target');
  window.addEventListener('scroll', handleScroll, { passive: true });
  window.addEventListener('touchstart', showTopBar, { passive: true });
  window.addEventListener('touchend', showTopBar, { passive: true });
  window.addEventListener('pointerup', showTopBar, { passive: true });
  window.addEventListener('scrollend', showTopBar, { passive: true });
  window.addEventListener('mousemove', showTopBar, { passive: true });
  window.addEventListener('keydown', showTopBar);

  showTopBar();
  })();
