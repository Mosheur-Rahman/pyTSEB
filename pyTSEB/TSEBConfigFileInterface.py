# This file is part PyTSEB, consisting of of high level pyTSEB scripting
# Copyright 2016 Hector Nieto and contributors listed in the README.md file.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from configparser import ConfigParser, NoOptionError
import itertools

from pyTSEB.PyTSEB import PyTSEB, PyTSEB2T, PyDTD, PydisTSEB


class ParserError(Exception):

    def __init__(self, parameter, expected_type):
        self.param = parameter
        self.type = expected_type


class MyConfigParser(ConfigParser):

    def __init__(self, top_section, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.section = top_section

    def get(self, option, *args, **kwargs):
        return super().get(self.section, option, *args, **kwargs)

    def getint(self, option, *args, **kwargs):
        try:
            val = super().getint(self.top_section, option, *args, **kwargs)
        except ValueError:
            raise ParserError(option, 'int')

        return val

    def getfloat(self, option, *args, **kwargs):
        try:
            val = super().getfloat(self.top_section, option, *args, **kwargs)
        except ValueError:
            raise ParserError(option, 'float')

        return val

    def has_option(self, option):
        return super().has_option(self.section, option)


class TSEBConfigFileInterface():

    SITE_DESCRIPTION = [
        'landcover',
        'lat',
        'lon',
        'alt',
        'stdlon',
        'z_T',
        'z_u',
        'z0_soil'
    ]

    VEGETATION_PROPERTIES = [
        'leaf_width',
        'alpha_PT',
        'x_LAD'
    ]

    SPECTRAL_PROPERTIES = [
        'emis_C',
        'emis_S',
        'rho_vis_C',
        'tau_vis_C',
        'rho_nir_C',
        'tau_nir_C',
        'rho_vis_S',
        'rho_nir_S'
    ]

    MODEL_FORMULATION = [
        'model',
        'resistance_form',
        'KN_b',
        'KN_c',
        'KN_C_dash',
        'G_form',
        'G_constant',
        'G_ratio',
        'G_amp',
        'G_phase',
        'G_shape',
        'calc_row',
        'row_az',
        'output_file',
        'correct_LST',
        'flux_LR_method'
    ]

    IMAGE_VARS = [
        'T_R1',
        'T_R0',
        'VZA',
        'LAI',
        'f_c',
        'f_g',
        'h_C',
        'w_C',
        'input_mask',
        'subset',
        'time',
        'DOY',
        'T_A1',
        'T_A0',
        'u',
        'ea',
        'S_dn',
        'L_dn',
        'p',
        'flux_LR',
        'flux_LR_ancillary'
    ]

    POINT_VARS = [
        'f_c',
        'f_g',
        'w_C'
    ]

    def __init__(self):

        self.params = {}
        self.ready = False

    @staticmethod
    def parse_input_config(input_file, **kwargs):
        ''' Parses the information contained in a configuration file into a dictionary'''

        parser = MyConfigParser()
        with open(input_file) as conf_file:
            conf_file = itertools.chain(('[top]',), conf_file)  # dummy section to please parser
            parser.read_file(conf_file)

        return parser

    @staticmethod
    def _parse_common_config(parser):
        """Parse all the stuff that's the same for image and point"""

        conf = {}

        conf['model'] = parser.get('model')
        conf['output_file'] = parser.get('output_file')

        conf['resistance_form'] = parser.getint('resistance_form', fallback=None)

        conf['calc_row'] = parser.getint('calc_row', fallback=[0, 0])
        if conf['calc_row'] != [0, 0]:
            row_az = parser.getfloat('row_az')
            conf['calc_row'] = [1, row_az]

        g_form = parser.getint('G_form', fallback=1)
        if g_form == 0:
            g_constant = parser.getfloat('G_constant')
            conf['G_form'] = [[0], g_constant]
        elif g_form == 2:
            g_params = [parser.getfloat(p) for p in ('G_amp', 'G_phase', 'G_shape')]
            conf['G_form'] = [[2, *g_params], 12.0]
        else:
            g_ratio = parser.getfloat('G_ratio')
            conf['G_form'] = [[1], g_ratio]

        if conf['model'] == 'disTSEB':
            conf['flux_LR_method'] = parser.get('flux_LR_method')
            conf['correct_LST'] = parser.getint('correct_LST')

        return conf

    @staticmethod
    def _parse_image_config(parser):
        """Parse the image specific things"""

        conf = {}

        # remaining in MODEL_FORMULATION
        conf.update({p: parser.get(p) for p in ['KN_b', 'KN_c', 'KN_C_dash']})

        conf.update({p: parser.get(p) for p in TSEBConfigFileInterface.SITE_DESCRIPTION})
        conf.update({p: parser.get(p) for p in TSEBConfigFileInterface.VEGETATION_PROPERTIES})
        conf.update({p: parser.get(p) for p in TSEBConfigFileInterface.SPECTRAL_PROPERTIES})

        img_vars = set(TSEBConfigFileInterface.IMAGE_VARS)
        if conf['model'] != 'DTD':
            img_vars -= set(['T_A0', 'T_R0'])
        if conf['model'] != 'disTSEB':
            img_vars -= set(['flux_LR', 'flux_LR_ancillary'])
        if not parser.has_option('subset'):
            img_vars.remove('subset')

        conf.update({p: parser.get(p) for p in img_vars})

        return conf

    @staticmethod
    def _parse_point_config(parser):
        """Parse the point specific things"""

        conf = {}

        # remaining in MODEL_FORMULATION
        conf.update({p: parser.getfloat(p) for p in ['KN_b', 'KN_c', 'KN_C_dash']})

        conf.update({p: parser.getfloat(p) for p in TSEBConfigFileInterface.SITE_DESCRIPTION})
        conf.update({p: parser.getfloat(p) for p in TSEBConfigFileInterface.VEGETATION_PROPERTIES})
        conf.update({p: parser.getfloat(p) for p in TSEBConfigFileInterface.SPECTRAL_PROPERTIES})

        conf['input_file'] = parser.get('input_file')
        conf.update({p: parser.get(p) for p in TSEBConfigFileInterface.POINT_VARS})

        return conf

    def get_data(self, parser, is_image):
        '''Parses the parameters in a configuration file directly to TSEB variables for running
           TSEB'''

        conf = self._parse_common_config(parser)

        try:
            if is_image:
                conf.update(self._parse_image_config(parser))
            else:
                conf.update(self._parse_point_config(parser))
            self.ready = True
        except NoOptionError as e:
            print(f'Error: missing parameter {e.option}')
        except ParserError as e:
            print(f'Error: could not parse parameter {e.param} as type {e.type}')

        self.params = conf

    def run(self, is_image):

        if self.ready:
            if self.params['model'] == "TSEB_PT":
                model = PyTSEB(self.params)
            elif self.params['model'] == "TSEB_2T":
                model = PyTSEB2T(self.params)
            elif self.params['model'] == "DTD":
                model = PyDTD(self.params)
            elif self.params['model'] == "disTSEB":
                model = PydisTSEB(self.params)
            else:
                print("Unknown model: " + self.params['model'] + "!")
                return None
            if is_image:
                model.process_local_image()
            else:
                in_data, out_data = model.process_point_series_array()
                return in_data, out_data
        else:
            print("pyTSEB will not be run due to errors in the input data.")
