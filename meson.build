project('universalcontrolkit',
          version: '0.1.0',
    meson_version: '>= 1.0.0',
  default_options: [ 'warning_level=2', 'werror=false', ],
)

i18n = import('i18n')
host_system = host_machine.system()
if host_system == 'linux'
  gnome = import('gnome')
endif

subdir('data')
subdir('src')
subdir('po')

if host_system == 'linux'
  gnome.post_install(
    update_desktop_database: true,
    gtk_update_icon_cache: true,
  )
endif
