pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'universalcontrolkit'
host_system = host_machine.system()
if host_system == 'linux'
  gnome = import('gnome')
endif

if host_system == 'linux'
  gnome.compile_resources('universalcontrolkit',
    'universalcontrolkit.gresource.xml',
    gresource_bundle: true,
    install: true,
    install_dir: pkgdatadir,
  )
endif

python = import('python')
py_installation = python.find_installation('python3')

conf = configuration_data()
conf.set('PYTHON', py_installation.full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'universalcontrolkit.in',
  output: 'universalcontrolkit',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

fs = import('fs')

# Find and install all Python files recursively
find_result = run_command('find', '.', '-name', '*.py', '-type', 'f', check: true)
all_py_files = find_result.stdout().strip().split('\n')

foreach file : all_py_files
  # Remove leading './'
  clean_path = file.substring(2)
  
  # Get directory path (everything before the filename)
  if clean_path.contains('/')
    dir_path = fs.parent(clean_path)
    install_subdir = 'universalcontrolkit' / dir_path
  else
    install_subdir = 'universalcontrolkit'
  endif
  
  py_installation.install_sources(clean_path, subdir: install_subdir)
endforeach
