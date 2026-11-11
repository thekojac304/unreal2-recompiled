/* Minimal math.h for the translated game code (see README.txt). */
#ifndef XRT_COMPAT_MATH_H
#define XRT_COMPAT_MATH_H
double fabs(double);
double floor(double);
double ceil(double);
double round(double);
double ldexp(double, int);
#define isnan(x) __builtin_isnan(x)
#endif
