/**
 * Mulberry E-Scooter Tours - Main JavaScript
 */
document.addEventListener('DOMContentLoaded', () => {
      const toggle = document.getElementById('navToggle');
      const menu = document.getElementById('navMenu');
      if (toggle && menu) {
                toggle.addEventListener('click', () => {
                              toggle.classList.toggle('active');
                              menu.classList.toggle('active');
                });
                menu.querySelectorAll('a').forEach(link => {
                              link.addEventListener('click', () => {
                                                toggle.classList.remove('active');
                                                menu.classList.remove('active');
                              });
                });
      }
      const navbar = document.getElementById('navbar');
      if (navbar) {
                window.addEventListener('scroll', () => {
                              navbar.style.boxShadow = window.scrollY > 50 ? '0 2px 12px rgba(0,0,0,.1)' : 'none';
                });
      }
      document.querySelectorAll('.flash').forEach(flash => {
                setTimeout(() => {
                              flash.style.transition = 'opacity .5s, transform .5s';
                              flash.style.opacity = '0';
                              flash.style.transform = 'translateX(100%)';
                              setTimeout(() => flash.remove(), 500);
                }, 6000);
      });
      document.querySelectorAll('input[type="tel"]').forEach(input => {
                input.addEventListener('input', (e) => {
                              let val = e.target.value.replace(/\\D/g, '');
                              if (val.length >= 10) val = `(${val.slice(0,3)}) ${val.slice(3,6)}-${val.slice(6,10)}`;
                              e.target.value = val;
                });
      });
      const today = new Date().toISOString().split('T')[0];
      document.querySelectorAll('input[type="date"]').forEach(input => { if (!input.min) input.min = today; });
});
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
                const target = document.querySelector(this.getAttribute('href'));
                if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
      });
});
