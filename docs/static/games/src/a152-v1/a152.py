"""a152 Body Boundary -- infer embodiment through probe-dependent co-motion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,CORE,LIMB,TOOL,PASSENGER,FOLLOWER,JOINT,CURSOR,GATE=3,8,12,10,14,13,7,9,11,4
BAD=15
TRUE_BODY=0b00101101
LEVELS=[
 {"name":"Mark Body Part","seq":(1,)},{"name":"Select Part","seq":(2,)},
 {"name":"Probe Joint","seq":(3,1)},{"name":"Compare Co-motion","seq":(1,2,3,4,2)},
 {"name":"Fit Through Gate","seq":(1,3,2,1,4,3,2)},{"name":"Body Boundary","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 marked,cursor,probe,correct,extras,width,history,snapshot=s
 if a==1:marked^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:probe=(probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:correct=(marked&TRUE_BODY).bit_count();extras=(marked&~TRUE_BODY).bit_count();width=1+correct//2+extras;history=(history+(4,))[-8:]
 elif a==5:snapshot=(marked,cursor,probe,correct,extras,width,history)
 return marked,cursor,probe,correct,extras,width,history,snapshot
for q in LEVELS:
 s=(0b00000001,0,0,1,0,1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER;pts=((30,28),(18,18),(30,14),(42,18),(18,38),(30,43),(42,38),(50,28));cols=(CORE,LIMB,LIMB,TOOL,LIMB,PASSENGER,FOLLOWER,FOLLOWER)
  for i,(x,y) in enumerate(pts):
   f[y-5:y+6,x-5:x+6]=cols[i]
   if (g.marked>>i)&1:f[y-2:y+3,x-2:x+3]=JOINT
   if i==g.cursor:f[y-8:y-6,x-6:x+7]=CURSOR
  f[9:52,55:59]=GATE;f[54:58,8:8+g.correct*6]=JOINT;f[7:10,8:8+g.extras*8]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A152(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a152",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.marked,self.cursor,self.probe,self.correct,self.extras,self.width,self.history,self.snapshot=(0b00000001,0,0,1,0,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.marked,self.cursor,self.probe,self.correct,self.extras,self.width,self.history,self.snapshot=advance((self.marked,self.cursor,self.probe,self.correct,self.extras,self.width,self.history,self.snapshot),a)
  elif a==6:
   if (self.marked,self.cursor,self.probe,self.correct,self.extras,self.width,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
