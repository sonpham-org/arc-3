"""q223 Impeller Veil -- schedule wake attention while redundant samples become costly."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,ROTOR,BLADE,FOCUS,SAMPLE,COST,BAD=2,3,4,9,15,10,11,8
LEVELS=[{"name":"Frozen Blade","plan":(1,4)},{"name":"Hidden Wake","plan":(2,1,4)},{"name":"First Sample","plan":(3,5,4,1)},{"name":"Coupled Rotors","plan":(1,5,2,4,3)},{"name":"Redundancy Cost","plan":(2,4,3,5,1,4)},{"name":"Impeller Veil","plan":(3,5,1,4,2,5,3,4)}]
def advance(s,a):
 rotors,focus,wake,samples,cost=s;rotors=list(rotors);samples=list(samples)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:rotors[i]=(rotors[i]+i+1+wake)%4
 elif a==4:rotors[focus]=(rotors[focus]+focus+wake+2)%4
 elif a==5:
  item=(tuple(rotors),focus,wake);cost+=2 if item in samples else 1;samples.append(item);wake=1-wake
 return tuple(rotors),focus,wake,tuple(samples),cost
def target(x):
 s=((0,1,2),0,0,(),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i,v in enumerate(g.rotors):x=8+i*18;f[10:35,x:x+14]=ROTOR;f[15+v*4:22+v*4,x+4:x+10]=BLADE
  f[7:10,8+g.focus*18:21+g.focus*18]=FOCUS;f[42:45,8:8+len(g.samples)*7]=SAMPLE;f[49:52,8:8+g.cost*7]=COST
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q223(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q223",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.rotors=(0,1,2);self.focus=self.wake=0;self.samples=();self.cost=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.rotors,self.focus,self.wake,self.samples,self.cost=advance((self.rotors,self.focus,self.wake,self.samples,self.cost),a)
  elif a==6:
   if (self.rotors,self.focus,self.wake,self.samples,self.cost)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
