"""a101 Diffraction Gate -- size apertures to shape wave spread behind walls."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,WALL,APERTURE,WAVE,RECEIVER,ABSORBER,SPREAD,ENERGY,BAD=13,8,9,12,14,10,4,11,6,15
LEVELS=[
 {"name":"Narrow Aperture","seq":(1,)},{"name":"Select Opening","seq":(3,)},
 {"name":"Wide Aperture","seq":(2,4)},{"name":"Illuminate Sides","seq":(1,3,2,4,1)},
 {"name":"Dark Absorber","seq":(1,4,3,2,4,1,4)},{"name":"Diffraction Gate","seq":(1,3,2,4,1,3,1,4,2,4)},
]
def advance(s,a):
 widths,cursor,phase,receivers,absorber,pulses,history,snapshot=s;w=list(widths);r=list(receivers)
 if a==1:w[cursor]=max(1,w[cursor]-1);history=(history+(1,))[-8:]
 elif a==2:w[cursor]=min(6,w[cursor]+1);history=(history+(2,))[-8:]
 elif a==3:cursor^=1;history=(history+(3,))[-8:]
 elif a==4:
  spread=7-w[cursor];r[cursor]=(r[cursor]+spread)%8;absorber=(absorber+max(0,w[cursor]-3))%7;phase^=1;pulses=(pulses+1)%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(w),cursor,phase,tuple(r),absorber,pulses,history)
 return tuple(w),cursor,phase,tuple(r),absorber,pulses,history,snapshot
for x in LEVELS:
 s=((4,3),0,0,(0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER;f[8:56,28:36]=WALL
  for i,w in enumerate(g.widths):y=17+i*25;f[y:y+w*2,28:36]=APERTURE;f[y-3:y+3,7:27]=WAVE
  for i,v in enumerate(g.receivers):y=13+i*28;f[y:y+11,47:58]=RECEIVER;f[y+2:y+9,49:49+v]=ENERGY
  f[27:38,38:47]=ABSORBER;f[7:11,8:8+g.pulses*6]=SPREAD;f[55:58,8:8+g.absorber*5]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A101(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a101",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.widths,self.cursor,self.phase,self.receivers,self.absorber,self.pulses,self.history,self.snapshot=((4,3),0,0,(0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.widths,self.cursor,self.phase,self.receivers,self.absorber,self.pulses,self.history,self.snapshot=advance((self.widths,self.cursor,self.phase,self.receivers,self.absorber,self.pulses,self.history,self.snapshot),a)
  elif a==6:
   if (self.widths,self.cursor,self.phase,self.receivers,self.absorber,self.pulses,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
