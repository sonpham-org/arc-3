"""q796 Crossing Rhythm -- combine marked clock projections before interrupting a ferry macro."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,TRACK,PASSENGER,MACRO,CLOCK0,CLOCK1,MARK0,MARK1,WINDOW,BAD=10,1,6,14,11,9,12,7,5,13,15
LEVELS=[
 {"name":"First View","periods":(2,3),"seq":(1,4,3,1,4)},
 {"name":"Second Tick","periods":(2,3),"seq":(2,4,3,1,4)},
 {"name":"Disjoint Clocks","periods":(3,4),"seq":(1,2,4,3,1,4)},
 {"name":"Marked Window","periods":(3,5),"seq":(1,4,3,2,1,4)},
 {"name":"Alternating Macro","periods":(4,5),"seq":(1,2,4,3,1,4,3,2,4)},
 {"name":"Crossing Rhythm","periods":(4,7),"seq":(1,4,3,1,2,4,3,2,1,4)}]
def advance(s,a,x,check=True):
 controller,p0,p1,macros,marks,interrupted=s
 if a==1:
  if controller==0:p0=(p0+2)%x["periods"][0]
  else:p1=(p1+3)%x["periods"][1]
  macros+=1
 elif a==2:
  if controller==0:p0=(p0+1)%x["periods"][0]
  else:p1=(p1+1)%x["periods"][1]
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,p0 if controller==0 else p1),)
 elif a==5:
  if check and ((p0,p1)!=x["window"] or {m[0] for m in marks}!={0,1}):return None
  interrupted=(controller,p0,p1,macros,marks[-2:])
 return controller,p0,p1,macros,marks,interrupted
for x in LEVELS:
 s=(0,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a,x,False);assert s is not None
 x["window"]=(s[1],s[2]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(12):x=7+(i%6)*9;y=10+(i//6)*12;f[y:y+5,x:x+5]=PASSENGER if i==(g.p0*3+g.p1)%12 else TRACK
  f[38:42,8:8+g.p0*10+8]=CLOCK0;f[45:49,8:8+g.p1*6+8]=CLOCK1
  for i,m in enumerate(g.marks[-4:]):f[52:56,8+i*11:16+i*11]=MARK0 if m[0]==0 else MARK1
  if g.macros:f[56:60,8:8+min(g.macros,6)*7]=MACRO
  if g.interrupted:f[55:59,43:56]=WINDOW
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q796(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q796",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=self.p0=self.p1=self.macros=0;self.marks=();self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.p0,self.p1,self.macros,self.marks,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.p0,self.p1,self.macros,self.marks,self.interrupted=s
  elif a==6:
   if (self.controller,self.p0,self.p1,self.macros,self.marks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
