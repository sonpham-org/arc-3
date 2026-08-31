"""a100 Waveguide Switch -- rotate guide sections to convert and pass modes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,GUIDE,MODE_A,MODE_B,JUNCTION,ROTATE,BRANCH,ENERGY,BAD=12,8,9,10,14,4,11,13,6,15
LEVELS=[
 {"name":"Rotate Section","seq":(1,)},{"name":"Select Section","seq":(2,)},
 {"name":"Toggle Input Mode","seq":(3,1)},{"name":"Launch Energy","seq":(1,2,1,4,3)},
 {"name":"Narrow Junction","seq":(3,1,2,1,4,2,4)},{"name":"Waveguide Switch","seq":(1,2,1,3,4,2,1,4,3,4)},
]
def advance(s,a):
 sections,cursor,input_mode,branches,launches,history,snapshot=s;sec=list(sections);br=list(branches)
 if a==1:sec[cursor]^=1;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:input_mode^=1;history=(history+(3,))[-8:]
 elif a==4:
  mode=input_mode
  for v in sec:mode^=v
  br[mode]=(br[mode]+1+sum(sec))%7;launches=(launches+1)%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(sec),cursor,input_mode,tuple(br),launches,history)
 return tuple(sec),cursor,input_mode,tuple(br),launches,history,snapshot
for x in LEVELS:
 s=((0,1,0,1,0),0,0,(0,0),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER;f[24:40,6:50]=GUIDE
  for i,v in enumerate(g.sections):x=8+i*8;f[20:44,x:x+7]=MODE_B if v else MODE_A
  f[19:45,49:54]=JUNCTION;f[13:26,54:59]=BRANCH;f[38:51,54:59]=BRANCH
  for i,v in enumerate(g.branches):f[15+i*25:23+i*25,55:58]=ENERGY if v else BRANCH
  f[8:12,8+g.cursor*8:15+g.cursor*8]=ROTATE;f[52:56,8:20]=MODE_A if g.input_mode==0 else MODE_B
  for i in range(g.launches):f[56:59,26+i*4:29+i*4]=ENERGY
  if g.bad:f[1:4,18:46]=BAD
  return f
class A100(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a100",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sections,self.cursor,self.input_mode,self.branches,self.launches,self.history,self.snapshot=((0,1,0,1,0),0,0,(0,0),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.sections,self.cursor,self.input_mode,self.branches,self.launches,self.history,self.snapshot=advance((self.sections,self.cursor,self.input_mode,self.branches,self.launches,self.history,self.snapshot),a)
  elif a==6:
   if (self.sections,self.cursor,self.input_mode,self.branches,self.launches,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
