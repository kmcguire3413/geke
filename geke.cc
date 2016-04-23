#include <python2.7/Python.h>
#include <stdio.h>
#include <limits>
#include <cmath>
#include <stdint.h>

#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>

#define RGB(R, G, B) (0xff << 24 | R << 16 | G << 8 | B)

static PyObject *geke_error;


class PyObjectW {
	public:
	PyObject *obj;

	PyObjectW(PyObject *obj) {
		this->obj = obj;
	}

	~PyObjectW() {
		Py_DECREF(this->obj);
	}
};

#define DW(x) (x.obj)
#define DW_DOUBLE(x) (PyFloat_AsDouble(DW(x))) 
#define DW_DOUBLE_GETITEM(x, y) (PyFloat_AsDouble(DW(PyObjectW(PySequence_GetItem((x), (y))))))
#define PYX_GETITEM_VALUE(f, a, i) (f(PyObjectW(PySequence_GetItem(a, i)).obj))
#define PYX_GETKEY_VALUE(f, a, k) (f(PyObjectW(PyObject_GetAttrString(a, k))))
#define ANGLEDIFF(th, lth) (fmod(((th) - (lth)) + M_PI, M_PI * 2.0) - M_PI);

/*
static PyObject *geke_spin_and_limit(PyObject *self, PyObject *args) {
	double 		rot_limit = PYX_GETKEY_VALUE(PyFloat_AsDouble, args, "rot_limit");
	double 		theta_inc = PYX_GETKEY_VALUE(PyFloat_AsDouble, args, "theta_inc");
	float 		lth = PYX_GETKEY_VALUE(PyFloat_AsDouble, args, "lth");
	float 		lmag = PYX_GETKEY_VALUE(PyFloat_AsDouble, args, "lmag");
	Py_buffer   *fft_filter = PYX_GETKEY_VALUE(PyMemoryView_GET_BUFFER, args, "fft_filter");

	PyObjectW   po_seq = PyObjectW(PySequence_GetItem(args, 0));

	float  		th = 0.0;
	float       mag = 0.0;

	NpyIter *iter = NpyIter_New((PyArrayObject*)DW(po_seq), 
		NPY_ITER_READWRITE | 
		NPY_ITER_EXTERNAL_LOOP | 
		NPY_ITER_ALIGNED, 
		NPY_KEEPORDER, 
		NPY_NO_CASTING, 
		NULL
	);

	NpyIter_IterNextFunc *iternext = NpyIter_GetIterNext(iter, NULL);
	double **dataptr = (double**)NpyIter_GetDataPtrArray(iter);
	npy_intp *strideptr = NpyIter_GetInnerStrideArray(iter);
	npy_intp *innersizeptr = NpyIter_GetInnerLoopSizePtr(iter);

	// hard limiting filter
	double   	adjusted = 0.0;
	int   		z = 0;
	double      thavg = 0.0;

	do {
		double *buf 		= *dataptr;
		npy_intp stride   	= *strideptr;
		npy_intp count      = *innersizeptr;

		printf("stride:%i count:%i\n", stride, count);

		for (int z = 0; z < count / 2; ++z) {
			//float   x = buf[z*2+0];
			//float   y = buf[z*2+1];
			double     x = buf[z*2+0];// * 6.0;
			double     y = buf[z*2+1];// * 6.0;

			th = atan2(y, x) + adjusted;
			mag = sqrt(x * x + y * y);

			//dth = th - lth
			//dth = math.fmod((dth + math.pi), math.pi * 2.0) - math.pi

			double dth = fmod((th - lth) + M_PI, M_PI * 2.0) - M_PI;

			double old_th = th;
			if (fabs(dth) > rot_limit) {
				th = lth;
			}

			if (z > 200 && z < 300) {
				printf("limited:%i z:%i th:%f old_th:%f lth:%f dth:%f rot_limit:%f\n", fabs(dth) > rot_limit, z, th, old_th, lth, dth, rot_limit);
			}

			buf[z*2+0] = cos(th + theta_inc * z) * mag;
			buf[z*2+1] = sin(th + theta_inc * z) * mag;

			lth = th;
			lmag = mag;
		}
	} while (iternext(iter));

	NpyIter_Deallocate(iter);

	PyObject *ret = PyTuple_Pack(2, PyFloat_FromDouble(th), PyFloat_FromDouble(mag));
	return ret;	
}
*/

static PyObject *geke_system(PyObject *self, PyObject *args) {
	//PyObjectW 	  po_state;
	//PyObjectW 	  po_seq;
	//PyObjectW 	  po_fftsize;
	//PyObjectW       po_width;
	//PyObjectW       po_yw;
	//PyObjectW       po_avg;
	//PyObjectW 	  po_bmpbuf;
	//PyObjectW 	  po_vwidth;

	int 			fftsize;
	double 			width;
	double          yw;
	double  		avg;
	unsigned int    *bmpbuf;
	unsigned int    vwidth;
	Py_ssize_t	    bmpbuflen;

	PyObjectW po_state = PyObjectW(PySequence_GetItem(args, 0));
	PyObjectW po_seq = PyObjectW(PySequence_GetItem(args, 1));
	PyObjectW po_fftsize = PyObjectW(PySequence_GetItem(args, 2));
	PyObjectW po_avg = PyObjectW(PySequence_GetItem(args, 3));
	PyObjectW po_bmpbuf = PyObjectW(PySequence_GetItem(args, 4));
	PyObjectW po_vwidth = PyObjectW(PySequence_GetItem(args, 5));
	double avg_low = PyFloat_AsDouble(DW(PyObjectW(PySequence_GetItem(DW(po_avg), 0))));
	double avg_high = PyFloat_AsDouble(DW(PyObjectW(PySequence_GetItem(DW(po_avg), 1))));

	//if (po_state & po_seq & po_fftsize & po_width & po_yw & po_avg & po_bmpbuf == 0) {
	//	PyErr_SetString(geke_error, "The arguments may not be NULL.");
	//	return NULL;
	//}

	bmpbuflen = 0;

	bmpbuflen = PyByteArray_Size(DW(po_bmpbuf));
	bmpbuf = (unsigned int*)PyByteArray_AsString(DW(po_bmpbuf));

	vwidth = (unsigned int)PyFloat_AsDouble(DW(po_vwidth));
	fftsize = PyLong_AsLong(DW(po_fftsize));

	NpyIter *iter = NpyIter_New((PyArrayObject*)DW(po_seq), NPY_ITER_READONLY, NPY_KEEPORDER, NPY_NO_CASTING, NULL);
	NpyIter_IterNextFunc *iternext = NpyIter_GetIterNext(iter, NULL);
	float **dataptr = (float**)NpyIter_GetDataPtrArray(iter);

	if (PyObject_GetAttrString(DW(po_state), "ly") == NULL) {
		PyObject *v = PyLong_FromLong(0);
		//Py_INCREF(v);
		PyObject_SetAttrString(DW(po_state), "ly", v);
	}

	long x = PyLong_AsLong(PyObject_GetAttrString(DW(po_state), "ly"));

	double high = std::numeric_limits<double>::min();
	double low = std::numeric_limits<double>::max();

	if (isinf(avg_low)) {
		avg_low = 0.0;
	}

	if (isinf(avg_high)) {
		avg_high = 0.0;
	}

	//printf("avg_low:%f avg_high:%f\n", avg_low, avg_high);

	do {
		/* Convert to the decibel scale. */
		double val = **dataptr;

		val = 30.0 * log10(val / 30.0);

		/* Get high and low per this FFT output chunk. */
		if (val > high) {
			high = val;
		}

		if (val < low) {
			low = val;
		}

		/* Normalize */
		val = (val - avg_low) / (high - avg_low);
		
		/* Clamp */
		if (val > 1.0) {
			val = 1.0;
		}

		if (val < 0.0) {
			val = 0.0;
		}

		bmpbuf[x] = RGB(int(val * 255.0), int(val * 255.0), int(val * 255.0));
		++x;

		if (vwidth < fftsize && x % fftsize == 0) {
			float whole = (float)fftsize / (float)vwidth;

			for (int b = 0; b < vwidth; ++b) {
				int from = int(b * whole);
				int limit = int(ceil(b * whole)) + 1;
				unsigned int high = 0;
				for (int q = from; q < limit; ++q) {
					int off = x - 1 - int(fftsize) + q;
					unsigned int tv = bmpbuf[off];
					if (tv > high) {
						high = tv;
					}
				}
				bmpbuf[b] = high;
			}
		}


		if (x >= bmpbuflen / 4) {
			x = 0;
		}
	} while (iternext(iter));

	for (int z = x; z < fftsize; ++z) {
		bmpbuf[z] = 0;
	}

	PyObject *ly = PyLong_FromLong(x);
	PyObject_SetAttrString(DW(po_state), "ly", ly);

	NpyIter_Deallocate(iter);

	avg_high = (avg_high * 20.0 + high) / 21.0;
	avg_low = (avg_low * 20.0 + low) / 21.0;

	PyObject *ret = PyTuple_Pack(2, PyFloat_FromDouble(avg_low), PyFloat_FromDouble(avg_high));
	return ret;
}

static PyMethodDef ModMethods[] = {
    { "system",  geke_system, METH_VARARGS, "A test method." },
    //{ "spin_and_limit", geke_spin_and_limit, METH_VARARGS, "Hard filter limit then rotator in one operation." },
    { NULL, NULL, 0, NULL }        /* Sentinel */
};

PyMODINIT_FUNC initgeke() {
	PyObject    *m;

	m = Py_InitModule("geke", ModMethods);
	import_array();

	geke_error = PyErr_NewException("geke.error", NULL, NULL);
	Py_INCREF(geke_error);
	PyModule_AddObject(m, "error", geke_error);	
}