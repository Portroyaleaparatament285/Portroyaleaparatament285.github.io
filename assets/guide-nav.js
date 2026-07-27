(function () {
  const topBar = document.getElementById('readerTopBar');
  if (!topBar) return;

  let scrollStopTimer = null;

  function showTopBar() {
    topBar.classList.remove('reader-hidden-top');
  }

  function hideTopBarWhileScrolling() {
    if (window.scrollY <= 20) {
      showTopBar();
      return;
    }

    topBar.classList.add('reader-hidden-top');
  }

  function handleScroll() {
    hideTopBarWhileScrolling();
    window.clearTimeout(scrollStopTimer);
    scrollStopTimer = window.setTimeout(showTopBar, 220);
  }

  topBar.classList.add('reader-auto-hide-target');
  window.addEventListener('scroll', handleScroll, { passive: true });
  window.addEventListener('touchstart', showTopBar, { passive: true });
  window.addEventListener('mousemove', showTopBar, { passive: true });
  window.addEventListener('keydown', showTopBar);
  showTopBar();
})();
