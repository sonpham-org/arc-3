"""a045 Barrier Beat -- release whole cohorts to synchronize unequal loops."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STAGE,LOOP,A1,A2,A3,BARRIER,PULSE,BEAT,BAD=5,9,8,12,14,10,11,13,6,15
LEVELS=[
 {"name":"First Beat","seq":(1,)},{"name":"Close Barrier","seq":(2,1)},
 {"name":"Gather Pair","seq":(1,2,1,3)},{"name":"Release Cohort","seq":(1,1,2,3,1)},
 {"name":"Unequal Loops","seq":(2,1,1,3,4,1,2)},{"name":"Barrier Beat","seq":(1,2,1,3,1,4,2,1,3)},
]
def advance(s,a):
 pos,waiting,phase,tempo,history,snapshot=s;p=list(pos);w=list(waiting)
 if a==1:
  for i in range(3):
   if not w[i]:
    p[i]=(p[i]+i+1+tempo)%12
    if p[i] in (0,6) and phase==(p[i]//6):w[i]=1
  history=(history+(1,))[-8:]
 elif a==2:phase^=1;history=(history+(2,))[-8:]
 elif a==3:
  for i in range(3):
   if w[i]:w[i]=0;p[i]=(p[i]+1)%12
  history=(history+(3,))[-8:]
 elif a==4:tempo=(tempo+1)%3;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),tuple(w),phase,tempo,history)
 return tuple(p),tuple(w),phase,tempo,history,snapshot
for x in LEVELS:
 s=((0,4,8),(0,0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  colors=(A1,A2,A3)
  for i,col in enumerate(colors):
   y=11+i*15;f[y:y+8,8:56]=LOOP
   x=9+(g.pos[i]%12)*4;f[y-2:y+10,x:x+4]=col
   if g.waiting[i]:f[y-3:y+11,31:35]=BARRIER
  f[7:54,30:32]=BARRIER if g.phase==0 else PULSE;f[7:54,34:36]=BARRIER if g.phase==1 else PULSE
  for i,v in enumerate(g.history[-8:]):f[55:58,10+i*5:14+i*5]=BEAT if v==1 else PULSE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A045(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a045",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.waiting,self.phase,self.tempo,self.history,self.snapshot=((0,4,8),(0,0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.waiting,self.phase,self.tempo,self.history,self.snapshot=advance((self.pos,self.waiting,self.phase,self.tempo,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.waiting,self.phase,self.tempo,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
