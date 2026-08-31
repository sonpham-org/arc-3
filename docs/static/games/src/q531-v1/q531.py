"""q531 Aurora Lesson -- infer a conditional demonstration through noise and hysteresis."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,DEMO,CONTEXT,HYSTERESIS,GOAL,BAD=0,10,12,14,6,11,4,7,15
def expected(rule,context,latent,hyst):return((rule+context+latent+hyst)%3)+1
def make(name,rule,d,n,switch,noise):
 context=latent=hyst=0;demo=[]
 for i in range(d):
  if i==switch:context=(context+1)%3;hyst=(hyst+2)%5
  a=0 if i==noise else expected(rule,context,latent,hyst);demo.append(a)
  if a:latent=(latent+a+rule+context)%5
  else:hyst=(hyst+1)%5
  hyst=(hyst+context+1)%5
 play=[]
 for _ in range(n):a=expected(rule,context,latent,hyst);play.append(a);latent=(latent+a+rule+context)%5;hyst=(hyst+context+1)%5
 return {"name":name,"rule":rule,"switch":switch,"demo":tuple(demo),"play":tuple(play),"plan":(4,)*d+(5,)+tuple(play)}
LEVELS=[make("Noisy Gesture",1,2,1,1,0),make("Context Curtain",2,3,1,1,2),make("Conditional Mote",3,3,2,1,0),make("Hysteretic Return",1,4,3,2,1),make("Long Demonstration",2,5,4,2,3),make("Aurora Lesson",3,6,5,3,1)]
def advance(s,a,x):
 context,latent,hyst,index,transferred,player,trace=s;trace=list(trace)
 if a==4 and not transferred:
  if index>=len(x["demo"]):return None
  if index==x["switch"]:context=(context+1)%3;hyst=(hyst+2)%5
  g=x["demo"][index];trace.append((0,g,context,hyst))
  if g:latent=(latent+g+x["rule"]+context)%5
  else:hyst=(hyst+1)%5
  hyst=(hyst+context+1)%5;index+=1
 elif a==5 and not transferred:transferred=True;trace.append((2,context,latent,hyst))
 elif a in (1,2,3) and transferred:
  if a!=expected(x["rule"],context,latent,hyst):return None
  trace.append((1,a,context,hyst));latent=(latent+a+x["rule"]+context)%5;hyst=(hyst+context+1)%5;player+=1
 else:return None
 return context,latent,hyst,index,transferred,player,tuple(trace)
def target(x):
 s=(0,0,0,0,False,0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,e in enumerate(g.trace[-8:]):x=9+(i%4)*12;y=11+(i//4)*10;f[y:y+6,x:x+9]=MOTE-(e[0]%3)
  f[37:40,8:11+g.context*14]=CONTEXT;f[44:47,8:11+g.hyst*9]=HYSTERESIS;f[51:54,8:24]=DEMO;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q531(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q531",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.latent=self.hyst=self.index=self.player=0;self.transferred=False;self.trace=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.context,self.latent,self.hyst,self.index,self.transferred,self.player,self.trace),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.context,self.latent,self.hyst,self.index,self.transferred,self.player,self.trace=s
  elif a==6:
   if (self.context,self.latent,self.hyst,self.index,self.transferred,self.player,self.trace)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
