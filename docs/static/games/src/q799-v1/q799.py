"""q799 Monsoon Rhythm -- interrupt rain macros at an unequal-clock phase pair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,RAIN,STORM,MACRO,CLOCK0,CLOCK1,MEMORY,WINDOW,BAD=10,1,6,14,11,9,12,7,13,15
LEVELS=[
 {"name":"First Drizzle","periods":(2,3),"seq":(2,)},{"name":"First Storm","periods":(2,3),"seq":(1,)},
 {"name":"Unequal Clocks","periods":(3,4),"seq":(1,2)},{"name":"Phase Memory","periods":(3,5),"seq":(1,3,2)},
 {"name":"Macro Weather","periods":(4,5),"seq":(1,1,2,3,1)},
 {"name":"Monsoon Rhythm","periods":(4,7),"seq":(1,2,1,3,2,1,3)}]
def advance(s,a,x,check=True):
 p0,p1,macros,memory,interrupted=s
 if a==1:p0=(p0+2)%x["periods"][0];p1=(p1+3)%x["periods"][1];macros+=1
 elif a==2:p0=(p0+1)%x["periods"][0]
 elif a==3:p1=(p1+1)%x["periods"][1]
 elif a==4:memory=memory+((p0,p1),)
 elif a==5:
  if check and ((p0,p1)!=x["window"] or not memory):return None
  interrupted=(p0,p1,macros,len(memory))
 return p0,p1,macros,memory,interrupted
for x in LEVELS:
 s=(0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a,x,False)
 x["window"]=(s[0],s[1]);x["plan"]=x["seq"]+(4,5)
def target(x):
 s=(0,0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(12):x=7+(i%6)*9;y=10+(i//6)*12;f[y:y+5,x:x+5]=STORM if i==(g.p0*3+g.p1)%12 else RAIN
  wx=7+((g.cfg["window"][0]*3+g.cfg["window"][1])%6)*9;wy=10+(((g.cfg["window"][0]*3+g.cfg["window"][1])%12)//6)*12;f[wy+6:wy+9,wx:wx+5]=WINDOW
  f[38:42,8:8+g.p0*9+7]=CLOCK0;f[45:49,8:8+g.p1*6+7]=CLOCK1
  if g.macros:f[52:56,8:8+min(g.macros,6)*7]=MACRO
  if g.memory:f[56:60,8:28]=MEMORY
  if g.interrupted:f[55:59,43:56]=WINDOW
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q799(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q799",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.p0=self.p1=self.macros=0;self.memory=();self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.p0,self.p1,self.macros,self.memory,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.p0,self.p1,self.macros,self.memory,self.interrupted=s
  elif a==6:
   if (self.p0,self.p1,self.macros,self.memory,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
