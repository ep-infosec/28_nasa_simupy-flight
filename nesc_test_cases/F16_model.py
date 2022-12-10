"""
===========
F16 Model
===========

This model integrates the F16 aerodynamics, propulsion, and inertia models which were
exchanged using the DaveML format. The corresponding modules were generated using the
``ProcessDaveML`` sub-module and ``process_NESC_DaveML.py`` script.

Since the aerodynamics model is based on a different interface than the simupy_flight's,
the ``tot_aero_forces_moments`` method is over-written to handle the computation
directly rather than using the simupy_flight framework. The control input routing is
used for both the aerodynamic control surfaces and the propulsion model.

"""

import F16_aero
import F16_prop
import F16_inertia
import numpy as np
import simupy_flight
from nesc_testcase_helper import ft_per_m, kg_per_slug


N_per_lbf = 4.44822

# Use the F16_aero parameter data from DaveML-generated file
# convert from english units to SI
S_A = F16_aero.sref / (ft_per_m**2)
b_l = F16_aero.bspan / ft_per_m
c_l = F16_aero.cbar / ft_per_m
a_l = b_l


class F16(simupy_flight.Vehicle):
    def __init__(self, CG_PCT_MAC=25, use_reported_value=True):
        # Use the F16_inertia parameter data from DaveML-generated file
        # convert from english units to SI
        inertia_output = F16_inertia.F16_inertia(CG_PCT_MAC)
        Ixx, Iyy, Izz, Izx, Ixy, Iyz = (
            inertia_output[:6] * kg_per_slug / (ft_per_m**2)
        )
        y_com, z_com, x_com = inertia_output[7:] / ft_per_m
        # the mass value from the DaveML file does not match the reported value;
        # we use the reported value by default
        if use_reported_value:
            m = 637.26 * kg_per_slug  # slug
        else:
            m = inertia_output[6] * kg_per_slug

        # initialize default vehicle data, including pointing to the propulsion model
        super().__init__(
            m=m,
            I_xx=Ixx,
            I_yy=Iyy,
            I_zz=Izz,
            I_xy=Ixy,
            I_yz=Iyz,
            I_xz=Izx,
            x_com=x_com,
            y_com=y_com,
            z_com=z_com,
            base_aero_coeffs=0.0,
            x_mrc=0.0,
            y_mrc=0.0,
            z_mrc=0.0,
            S_A=S_A,
            a_l=a_l,
            b_l=b_l,
            c_l=c_l,
            d_l=0.0,
            # the input_force_moment callback is used for the propulsion model
            input_force_moment=self.prop_model,
            # allocate control signals for the elevator, aileron, rudder, and throttle
            dim_additional_input=4,
            # route the control surfaces to the aerodynamics model
            input_aero_coeffs_idx=slice(None, 3),
            # route the throttle to the propulsion model
            input_force_moment_idx=[3],
        )

    def tot_aero_forces_moments(
        self,
        qbar,
        Ma,
        Re,
        V_T,
        alpha,
        beta,
        p_B,
        q_B,
        r_B,
        el,
        ail,
        rdr,
    ):
        # use F16_aero model from DaveML-generated file. Inputs converted to english
        # units. Control surfaces input signals are routed and used here.
        cbar, bspan, sref, cx, cy, cz, cl, cm, cn = F16_aero.F16_aero(
            V_T * ft_per_m,
            alpha * 180 / np.pi,
            beta * 180 / np.pi,
            p_B,
            q_B,
            r_B,
            el,
            ail,
            rdr,
        )
        forces_moments = np.empty(6)
        body_force_coeffs = np.array([cx, cy, cz])
        body_moment_coeffs = np.array([cl, cm, cn])
        dynamic_force = qbar * self.S_A
        ref_lengths = np.array([self.a_l, self.c_l, self.b_l])
        forces_moments[:3] = dynamic_force * body_force_coeffs
        forces_moments[3:] = (dynamic_force * ref_lengths * body_moment_coeffs) - (
            simupy_flight.dynamics.mrc_to_com_cpm(self) @ forces_moments[:3]
        )
        return forces_moments

    def prop_model(self, *args):
        # use F16_prop model from DaveML-generated file.

        throttle = args[-1]
        alt = args[simupy_flight.Vehicle.h_D_arg_idx] * ft_per_m
        Ma = args[simupy_flight.Vehicle.Ma_arg_idx]
        return F16_prop.F16_prop(throttle, alt, Ma) * N_per_lbf
